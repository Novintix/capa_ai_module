"""
Unified Root Cause Analysis v2 Orchestrator (LangGraph).

Design goals:
- One parent RCA graph handles Fishbone + Why directly.
- Redis-backed checkpointing with session_id as thread_id.
- Two HITL pause points:
  1) fishbone cause selection
  2) why decision (continue | root_cause)
- No action-planning step in RCA v2.
"""

from __future__ import annotations

import datetime
import functools
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph

from Agents.categorize.graph import categorize_graph
from Agents.categorize.state import CategorizeInput, CategorizeState, Cause as CategorizeCause
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.cause_generation.schemas import QuestionInput
from Agents.question.agent import WhyQuestionAgent
from Agents.question.schemas import ContinueWhyInput, StartWhyInput
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import GeneratedCause, ValidationInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent
from Agents.zero_evidence_agent.schemas import CauseInput as ZeroEvidenceCauseInput
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput

from orchestrator.Root_cause_analysis.logger import log_error, log_info, log_transition
from .state_v2 import RCAV2GraphState

try:
    from config.redis_config import REDIS_URL as _REDIS_URL
except Exception:
    _REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


QUALIFIED_CONFIDENCE = 0.90
MAX_NODE_RETRIES = int(os.getenv("RCA_V2_NODE_RETRIES", "1"))
MAX_AGENT_LOG_CHARS = int(os.getenv("RCA_V2_AGENT_LOG_CHARS", "12000"))
# default_ttl is in MINUTES in langgraph-checkpoint-redis v0.4.x
RCA_V2_SESSION_TTL_MINUTES = int(os.getenv("RCA_V2_SESSION_TTL_MINUTES", str(7 * 24 * 60)))  # 7 days
RCA_V2_LOG_ROOT = os.path.join(os.path.dirname(__file__), "logs")
RCA_V2_AGENT_IO_LOG_FILE = os.path.join(
    RCA_V2_LOG_ROOT,
    os.getenv("RCA_V2_AGENT_IO_LOG_FILE", "agent_input_output.jsonl"),
)
RCA_V2_FILE_DEBUG_LOG_ENABLED = os.getenv("RCA_V2_FILE_DEBUG_LOG_ENABLED", "1") != "0"
RCA_V2_FILE_LOG_MAX_VALUE_CHARS = int(os.getenv("RCA_V2_FILE_LOG_MAX_VALUE_CHARS", "200000"))


_question_agent: Optional[WhyQuestionAgent] = None
_cause_agent: Optional[CauseGenerationAgent] = None
_validation_agent: Optional[ValidationAgent] = None
_zero_evidence_agent: Optional[ZeroEvidenceAgent] = None


def _get_question_agent() -> WhyQuestionAgent:
    global _question_agent
    if _question_agent is None:
        _question_agent = WhyQuestionAgent()
    return _question_agent


def _get_cause_agent() -> CauseGenerationAgent:
    global _cause_agent
    if _cause_agent is None:
        _cause_agent = CauseGenerationAgent()
    return _cause_agent


def _get_validation_agent() -> ValidationAgent:
    global _validation_agent
    if _validation_agent is None:
        _validation_agent = ValidationAgent()
    return _validation_agent


def _get_zero_evidence_agent() -> ZeroEvidenceAgent:
    global _zero_evidence_agent
    if _zero_evidence_agent is None:
        _zero_evidence_agent = ZeroEvidenceAgent()
    return _zero_evidence_agent


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def deep_serialize(obj: Any) -> Any:
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return deep_serialize(obj.model_dump(mode="json"))
        except Exception:
            try:
                return deep_serialize(obj.model_dump())
            except Exception:
                return str(obj)
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return deep_serialize(obj.dict())
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [deep_serialize(v) for v in obj]
    return obj


def _to_state_payload(payload: Any) -> Dict[str, Any]:
    serialized = deep_serialize(payload)
    if isinstance(serialized, dict):
        return serialized
    return {"value": serialized}


def _serialize_for_log(payload: Any) -> str:
    try:
        text = json.dumps(deep_serialize(payload), ensure_ascii=True, default=str)
    except Exception:
        text = str(payload)
    if len(text) > MAX_AGENT_LOG_CHARS:
        return text[:MAX_AGENT_LOG_CHARS] + "...<truncated>"
    return text


def _safe_slug(value: str) -> str:
    cleaned = [ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value]
    slug = "".join(cleaned).strip("_")
    return slug or "unknown"


def _truncate_long_strings(obj: Any) -> Any:
    if isinstance(obj, str):
        if len(obj) > RCA_V2_FILE_LOG_MAX_VALUE_CHARS:
            return obj[:RCA_V2_FILE_LOG_MAX_VALUE_CHARS] + "...<truncated>"
        return obj
    if isinstance(obj, list):
        return [_truncate_long_strings(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _truncate_long_strings(value) for key, value in obj.items()}
    return obj


def _extract_payload_field(payload: Any, field_name: str, default: str = "") -> str:
    if payload is None:
        return default
    if isinstance(payload, dict):
        return _safe_text(payload.get(field_name), default)
    if hasattr(payload, field_name):
        return _safe_text(getattr(payload, field_name), default)
    return default


def _write_structured_log(event_type: str, context: Dict[str, Any], payload: Any) -> None:
    if not RCA_V2_FILE_DEBUG_LOG_ENABLED:
        return

    # allow both agent and node related event types to be written
    if event_type not in ("agent_input", "agent_output", "node_input", "node_output", "node_exception"):
        return

    try:
        os.makedirs(RCA_V2_LOG_ROOT, exist_ok=True)

        event_record = {
            "timestamp": _now(),
            "event_type": event_type,
            "agent": _safe_text(context.get("agent")),
            "direction": _safe_text(context.get("direction")),
            "complaint_id": _safe_text(context.get("complaint_id")),
            "session_id": _safe_text(context.get("session_id")),
            "node": _safe_text(context.get("node")),
            "payload": _truncate_long_strings(deep_serialize(payload)),
        }

        with open(RCA_V2_AGENT_IO_LOG_FILE, "a", encoding="utf-8") as file_handle:
            json.dump(event_record, file_handle, ensure_ascii=True, indent=2)
            file_handle.write("\n")
    except Exception as exc:
        log_error("rca_v2_structured_log", str(exc), _safe_text(context.get("complaint_id")))


def _log_agent_io(agent_name: str, direction: str, payload: Any, context: Optional[Dict[str, Any]] = None) -> None:
    message = f"[RCA_V2][{agent_name}] {direction}: {_serialize_for_log(payload)}"
    print(message)
    log_info(message)
    effective_context = dict(context or {})
    if not effective_context.get("complaint_id"):
        effective_context["complaint_id"] = _extract_payload_field(payload, "complaint_id")
    if not effective_context.get("session_id"):
        effective_context["session_id"] = _extract_payload_field(payload, "session_id")
    effective_context.setdefault("agent", agent_name)
    effective_context.setdefault("direction", direction)
    _write_structured_log(f"agent_{direction}", effective_context, payload)


def _call_with_debug(agent_name: str, fn, payload: Any, *args, context: Optional[Dict[str, Any]] = None):
    _log_agent_io(agent_name, "input", payload, context=context)
    result = _retry_call(fn, payload, *args)
    _log_agent_io(agent_name, "output", result, context=context)
    return result


def _node_logging_wrapper(node_name: str, node_fn):
    @functools.wraps(node_fn)
    def _wrapped(state: RCAV2GraphState) -> Dict[str, Any]:
        base_context = {
            "node": node_name,
            "complaint_id": _safe_text(state.get("complaint_id")),
            "session_id": _safe_text(state.get("session_id")),
            "phase": _safe_text(state.get("phase")),
        }
        _write_structured_log("node_input", base_context, state)
        try:
            result = node_fn(state)
        except Exception as exc:
            _write_structured_log("node_exception", base_context, {"error": str(exc)})
            raise
        _write_structured_log("node_output", base_context, result)
        return result

    return _wrapped


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _safe_int(value: Any, default: int = 5) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalized_cause(cause: Dict[str, Any], fallback_id: str) -> Dict[str, Any]:
    return {
        "cause_id": _safe_text(cause.get("cause_id"), fallback_id),
        "cause_text": _safe_text(cause.get("cause_text"), "Unspecified cause description"),
        "process_step": _safe_text(cause.get("process_step"), "Unknown process step"),
        "failure_mode": _safe_text(cause.get("failure_mode"), "Unspecified failure mode"),
        "potential_effects": _safe_text(cause.get("potential_effects"), "Not provided"),
        "severity": _safe_int(cause.get("severity"), 5),
        "occurrence": _safe_int(cause.get("occurrence"), 5),
        "detection": _safe_int(cause.get("detection"), 5),
        "current_controls": _safe_text(cause.get("current_controls"), "Not provided"),
        "source": _safe_text(cause.get("source"), "Generated"),
        "category": _safe_text(cause.get("category"), "Unknown"),
        "category_confidence": _safe_float(cause.get("category_confidence"), 0.0),
        "category_reasoning": _safe_text(cause.get("category_reasoning"), ""),
        "secondary_categories": cause.get("secondary_categories") or [],
        "validation_status": _safe_text(cause.get("validation_status"), "not_matched"),
        "validation_confidence": _safe_float(cause.get("validation_confidence"), 0.0),
        "validation_rationale": _safe_text(cause.get("validation_rationale"), ""),
    }


def _build_fallback_causes(context: str) -> List[Dict[str, Any]]:
    base = _safe_text(context, "the observed issue")
    return [
        {
            "cause_id": "C001",
            "cause_text": f"Process control drift impacting: {base}",
            "process_step": "Process execution",
            "failure_mode": "Parameter drift",
            "potential_effects": "Output outside specification",
            "severity": 8,
            "occurrence": 5,
            "detection": 5,
            "current_controls": "Tighten process monitoring and alerting",
            "source": "Fallback_Generated",
        },
        {
            "cause_id": "C002",
            "cause_text": "Procedure execution inconsistency",
            "process_step": "Operator workflow",
            "failure_mode": "Missed critical step",
            "potential_effects": "Recurring defect pattern",
            "severity": 7,
            "occurrence": 6,
            "detection": 4,
            "current_controls": "Reinforce checklist and verification gate",
            "source": "Fallback_Generated",
        },
    ]


def _build_evidence_context(state: RCAV2GraphState) -> Dict[str, Any]:
    context: Dict[str, Any] = {"evidence": _safe_text(state.get("evidence"), "")}
    for field in (
        "sop",
        "logs",
        "reports",
        "process_data",
        "historical_capa",
        "policies",
        "investigation_records",
        "supporting_system_information",
    ):
        value = state.get(field)
        if value is not None:
            context[field] = value
    return context


def _build_zero_evidence_investigation_text(state: RCAV2GraphState) -> str:
    parts: List[str] = []
    primary_evidence = _safe_text(state.get("evidence"), "")
    if primary_evidence:
        parts.append(f"evidence: {primary_evidence}")

    for field in (
        "logs",
        "reports",
        "process_data",
        "historical_capa",
        "policies",
        "investigation_records",
        "supporting_system_information",
    ):
        value = state.get(field)
        if value is None:
            continue
        parts.append(f"{field}: {value}")

    if not parts:
        return ""

    # Keep payload bounded while still providing useful context.
    return "\n".join(parts)[:8000]


def _build_validation_input(
    state: RCAV2GraphState,
    question: str,
    causes: List[Dict[str, Any]],
) -> ValidationInput:
    generated_causes = [
        GeneratedCause(
            cause_id=_safe_text(c.get("cause_id"), f"C-{idx + 1:03d}"),
            cause_text=_safe_text(c.get("cause_text"), "Unspecified cause"),
            process_step=c.get("process_step"),
            failure_mode=c.get("failure_mode"),
            potential_effects=c.get("potential_effects"),
            severity=_safe_int(c.get("severity"), 5),
            occurrence=_safe_int(c.get("occurrence"), 5),
            detection=_safe_int(c.get("detection"), 5),
            current_controls=c.get("current_controls"),
            source=_safe_text(c.get("source"), "Generated"),
        )
        for idx, c in enumerate(causes)
    ]

    return ValidationInput(
        complaint_id=_safe_text(state.get("complaint_id")),
        question=question,
        generated_causes=generated_causes,
        complaint_description=_safe_text(state.get("complaint")),
        logs=state.get("logs"),
        reports=state.get("reports"),
        process_data=state.get("process_data"),
        historical_capa=state.get("historical_capa"),
        policies=state.get("policies"),
        sop=state.get("sop"),
        investigation_records=state.get("investigation_records"),
        supporting_system_information=state.get("supporting_system_information"),
        investigation_evidence={
            "evidence_text": _safe_text(state.get("evidence"), ""),
            "evidence_files": state.get("evidence_files") or [],
        },
    )


def _merge_validation(
    causes: List[Dict[str, Any]],
    validation_result: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    serialized = deep_serialize(validation_result)
    result_map: Dict[str, Dict[str, Any]] = {}
    for item in serialized.get("cause_validation_results") or []:
        cause_id = _safe_text(item.get("cause_id"), "")
        if cause_id:
            result_map[cause_id] = item

    merged: List[Dict[str, Any]] = []
    validated: List[Dict[str, Any]] = []
    qualified: List[Dict[str, Any]] = []

    for idx, raw in enumerate(causes):
        base = _normalized_cause(raw, f"C-{idx + 1:03d}")
        r = result_map.get(base["cause_id"], {})
        base["validation_status"] = _safe_text(
            r.get("evidence_match_status") or r.get("validation_status"),
            base.get("validation_status", "not_matched"),
        )
        base["validation_confidence"] = _safe_float(
            r.get("confidence") or r.get("validation_confidence"),
            base.get("validation_confidence", 0.0),
        )
        base["validation_rationale"] = _safe_text(
            r.get("rationale") or r.get("validation_rationale"),
            base.get("validation_rationale", ""),
        )

        merged.append(base)

        status = _safe_text(base.get("validation_status"), "").lower()
        if status in ("matched", "partially_matched"):
            validated.append(base)

        if (
            base.get("validation_confidence", 0.0) >= QUALIFIED_CONFIDENCE
            and status == "matched"
        ):
            qualified.append(base)

    return merged, validated, qualified


def _select_cause_by_id(causes: List[Dict[str, Any]], cause_id: str) -> Optional[Dict[str, Any]]:
    for cause in causes:
        if _safe_text(cause.get("cause_id")) == cause_id:
            return cause
    return None


def _build_zero_evidence_input(
    state: RCAV2GraphState,
    problem: str,
    complaint_id: str,
    causes: List[Dict[str, Any]],
) -> ZeroEvidenceInput:
    zero_causes = [
        ZeroEvidenceCauseInput(
            cause_id=_safe_text(c.get("cause_id"), f"ZE-{idx + 1:03d}"),
            cause_text=_safe_text(c.get("cause_text"), "Unspecified cause"),
            process_step=_safe_text(c.get("process_step"), "Unknown process step"),
            failure_mode=_safe_text(c.get("failure_mode"), "Unspecified failure mode"),
            potential_effects=c.get("potential_effects"),
            category=_safe_text(c.get("category"), "Unknown"),
            severity=_safe_int(c.get("severity"), 5),
            occurrence=_safe_int(c.get("occurrence"), 5),
            detection=_safe_int(c.get("detection"), 5),
            current_controls=c.get("current_controls"),
            source=_safe_text(c.get("source"), "Generated"),
        )
        for idx, c in enumerate(causes)
    ]

    return ZeroEvidenceInput(
        question_id=complaint_id,
        complaint_id=complaint_id,
        question=problem,
        complaint_description=_safe_text(state.get("complaint"), problem),
        investigation_evidence=_build_zero_evidence_investigation_text(state),
        causes=zero_causes,
        total_causes=len(zero_causes),
    )


def _retry_call(fn, *args):
    last_exc: Optional[Exception] = None
    for attempt in range(1 + MAX_NODE_RETRIES):
        try:
            return fn(*args)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES:
                log_error("rca_v2_retry", f"Attempt {attempt + 1} failed: {exc}")
                time.sleep(1)
    raise last_exc


# ══════════════════════════════════════════════════════════════════════════════
# NODE: initialize
# ══════════════════════════════════════════════════════════════════════════════

def initialize_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    complaint = _safe_text(state.get("complaint"))
    method = _safe_text(state.get("method"))
    session_id = _safe_text(state.get("session_id"))

    if not complaint_id:
        return {
            "status": "error",
            "phase": "error",
            "error": "complaint_id is required",
            "node_log": [{"node": "initialize", "status": "error", "timestamp": _now()}],
        }
    if not complaint:
        return {
            "status": "error",
            "phase": "error",
            "error": "complaint is required",
            "node_log": [{"node": "initialize", "status": "error", "timestamp": _now()}],
        }
    if method not in ("fishbone", "why"):
        return {
            "status": "error",
            "phase": "error",
            "error": "method must be either 'fishbone' or 'why'",
            "node_log": [{"node": "initialize", "status": "error", "timestamp": _now()}],
        }

    question_agent_session_id = f"{complaint_id}__{session_id}" if session_id else complaint_id

    return {
        "status": "running",
        "phase": "initialized",
        "awaiting_human_review": False,
        "hitl_type": None,
        "message": f"RCA v2 initialized with method={method}",
        "question_agent_session_id": question_agent_session_id,
        "active_problem_text": complaint,
        "fishbone_cause_generation_input": None,
        "fishbone_cause_generation_output": None,
        "fishbone_categorize_input": None,
        "fishbone_categorize_output": None,
        "fishbone_validation_input": None,
        "fishbone_validation_output": None,
        "fishbone_zero_evidence_input": None,
        "fishbone_zero_evidence_output": None,
        "fishbone_all_causes": [],
        "fishbone_categorized_causes": [],
        "fishbone_validated_causes": [],
        "fishbone_qualified_causes": [],
        "fishbone_candidate_causes": [],
        "fishbone_category_summary": {},
        "fishbone_zero_evidence_result": None,
        "fishbone_recommended_cause_id": None,
        "why_depth": 0,
        "why_question_start_input": None,
        "why_question_continue_input": None,
        "why_question_output": None,
        "why_cause_generation_input": None,
        "why_cause_generation_output": None,
        "why_validation_input": None,
        "why_validation_output": None,
        "why_zero_evidence_input": None,
        "why_zero_evidence_output": None,
        "why_current_causes": [],
        "why_validated_causes": [],
        "why_qualified_causes": [],
        "why_candidate_causes": [],
        "why_requires_zero_evidence": False,
        "final_root_cause": None,
        "why_question_calls": [],
        "why_cause_generation_calls": [],
        "why_validation_calls": [],
        "why_zero_evidence_calls": [],
        "node_log": [{"node": "initialize", "status": "success", "timestamp": _now()}],
        "timeline": [{"step": "initialize", "timestamp": _now(), "detail": f"method={method}"}],
        "audit_log": [{"time": time.time(), "action": "initialized", "detail": f"method={method}"}],
        "updated_at": time.time(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FISHBONE NODES
# ══════════════════════════════════════════════════════════════════════════════

def fishbone_generate_causes_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    complaint = _safe_text(state.get("complaint"))

    try:
        question_input = QuestionInput(
            question_id=f"{complaint_id}_fishbone",
            question=f"What are the potential causes of: {complaint}",
            context=complaint,
            evidence_context=_build_evidence_context(state),
        )
        fmea_path = state.get("fmea_document_path")
        if isinstance(fmea_path, str) and fmea_path and not os.path.isabs(fmea_path):
            fmea_path = os.path.abspath(fmea_path)
        if isinstance(fmea_path, str) and fmea_path and not os.path.exists(fmea_path):
            fmea_path = None

        cause_input_payload = _to_state_payload(question_input)
        cause_input_payload["fmea_document_path"] = fmea_path

        result = _call_with_debug(
            "CauseGenerationAgent.process_question",
            _get_cause_agent().process_question,
            question_input,
            fmea_path,
            context={
                "node": "fishbone_generate_causes",
                "complaint_id": complaint_id,
                "session_id": _safe_text(state.get("session_id")),
            },
        )
        causes = [
            _normalized_cause(c, f"C-{idx + 1:03d}")
            for idx, c in enumerate((deep_serialize(result).get("causes") or []))
        ]
        if not causes:
            causes = _build_fallback_causes(complaint)

        cause_output_payload = _to_state_payload(result)

        return {
            "phase": "fishbone_causes_generated",
            "fishbone_cause_generation_input": cause_input_payload,
            "fishbone_cause_generation_output": cause_output_payload,
            "fishbone_all_causes": causes,
            "node_log": [{"node": "fishbone_generate_causes", "status": "success", "count": len(causes), "timestamp": _now()}],
            "timeline": [{"step": "fishbone_generate_causes", "count": len(causes), "timestamp": _now()}],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("fishbone_generate_causes_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Fishbone cause generation failed: {exc}",
            "node_log": [{"node": "fishbone_generate_causes", "status": "error", "timestamp": _now()}],
            "timeline": [{"step": "fishbone_generate_causes", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def fishbone_categorize_node(state: RCAV2GraphState) -> Dict[str, Any]:
    causes = state.get("fishbone_all_causes") or []
    complaint = _safe_text(state.get("complaint"))
    complaint_id = _safe_text(state.get("complaint_id"))

    try:
        if not causes:
            return {
                "status": "error",
                "phase": "error",
                "error": "Fishbone categorization cannot run with 0 causes",
                "node_log": [{"node": "fishbone_categorize", "status": "error", "timestamp": _now()}],
            }

        categorize_input = CategorizeInput(
            question=complaint,
            causes=[
                CategorizeCause(
                    cause_id=c["cause_id"],
                    cause_text=c["cause_text"],
                    process_step=c.get("process_step"),
                    failure_mode=c.get("failure_mode"),
                    potential_effects=c.get("potential_effects"),
                    severity=c.get("severity"),
                    occurrence=c.get("occurrence"),
                    detection=c.get("detection"),
                    current_controls=c.get("current_controls"),
                    source=c.get("source"),
                )
                for c in causes
            ],
        )
        categorize_input_payload = _to_state_payload(categorize_input)
        categorize_state = CategorizeState(input=categorize_input, iteration=0)
        output_state = _call_with_debug(
            "CategorizeGraph.invoke",
            categorize_graph.invoke,
            categorize_state,
            context={
                "node": "fishbone_categorize",
                "complaint_id": complaint_id,
                "session_id": _safe_text(state.get("session_id")),
            },
        )
        final_output = output_state.get("final_output")

        categorized = [dict(c) for c in causes]
        summary: Dict[str, int] = {}

        if final_output:
            mapping = {item.cause_id: item for item in final_output.categorized_causes}
            for cause in categorized:
                item = mapping.get(cause.get("cause_id"))
                if item:
                    cause["category"] = item.category
                    cause["category_confidence"] = float(item.confidence)
                    cause["category_reasoning"] = item.reasoning
                    cause["secondary_categories"] = item.secondary_categories
                else:
                    cause["category"] = cause.get("category", "Unknown") or "Unknown"
                    cause["category_confidence"] = float(cause.get("category_confidence") or 0.0)
                    cause["category_reasoning"] = cause.get("category_reasoning") or ""
                    cause["secondary_categories"] = cause.get("secondary_categories") or []
            summary = dict(final_output.summary or {})
        else:
            for cause in categorized:
                cause["category"] = cause.get("category", "Unknown") or "Unknown"
                cause["category_confidence"] = float(cause.get("category_confidence") or 0.0)
                cause["category_reasoning"] = cause.get("category_reasoning") or ""
                cause["secondary_categories"] = cause.get("secondary_categories") or []
                summary[cause["category"]] = summary.get(cause["category"], 0) + 1

        categorize_output_payload = {
            "categorized_causes": deep_serialize(categorized),
            "summary": deep_serialize(summary),
        }

        return {
            "phase": "fishbone_categorized",
            "fishbone_categorize_input": categorize_input_payload,
            "fishbone_categorize_output": categorize_output_payload,
            "fishbone_categorized_causes": categorized,
            "fishbone_category_summary": summary,
            "node_log": [{"node": "fishbone_categorize", "status": "success", "timestamp": _now()}],
            "timeline": [{"step": "fishbone_categorize", "timestamp": _now(), "summary": summary}],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("fishbone_categorize_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Fishbone categorization failed: {exc}",
            "node_log": [{"node": "fishbone_categorize", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def fishbone_validate_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    complaint = _safe_text(state.get("complaint"))
    categorized = state.get("fishbone_categorized_causes") or state.get("fishbone_all_causes") or []

    try:
        validation_input = _build_validation_input(state, complaint, categorized)
        validation_input_payload = _to_state_payload(validation_input)
        validation_result = _call_with_debug(
            "ValidationAgent.validate_causes",
            _get_validation_agent().validate_causes,
            validation_input,
            context={
                "node": "fishbone_validate",
                "complaint_id": complaint_id,
                "session_id": _safe_text(state.get("session_id")),
            },
        )
        validation_output_payload = _to_state_payload(validation_result)
        merged, validated, qualified = _merge_validation(categorized, validation_result)

        return {
            "phase": "fishbone_validated",
            "fishbone_validation_input": validation_input_payload,
            "fishbone_validation_output": validation_output_payload,
            "fishbone_validated_causes": merged,
            "fishbone_qualified_causes": qualified,
            "node_log": [{
                "node": "fishbone_validate",
                "status": "success",
                "total": len(merged),
                "qualified": len(qualified),
                "timestamp": _now(),
            }],
            "timeline": [{
                "step": "fishbone_validate",
                "total": len(merged),
                "qualified": len(qualified),
                "timestamp": _now(),
            }],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("fishbone_validate_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Fishbone validation failed: {exc}",
            "node_log": [{"node": "fishbone_validate", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def fishbone_prepare_selection_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    qualified = state.get("fishbone_qualified_causes") or []
    candidates: List[Dict[str, Any]]
    recommended_cause_id: Optional[str] = None
    zero_result: Optional[Dict[str, Any]] = None
    zero_input_payload: Optional[Dict[str, Any]] = None
    zero_output_payload: Optional[Dict[str, Any]] = None

    try:
        if qualified:
            candidates = [dict(c) for c in qualified]
            sorted_candidates = sorted(
                candidates,
                key=lambda c: _safe_float(c.get("validation_confidence"), 0.0),
                reverse=True,
            )
            if sorted_candidates:
                recommended_cause_id = _safe_text(sorted_candidates[0].get("cause_id"), None)
            message = (
                f"Select exactly one qualified fishbone cause ({len(candidates)} available) to start Why analysis."
            )
        else:
            candidates = [
                dict(c)
                for c in (
                    state.get("fishbone_validated_causes")
                    or state.get("fishbone_categorized_causes")
                    or state.get("fishbone_all_causes")
                    or []
                )
            ]
            if candidates:
                zero_input = _build_zero_evidence_input(
                    state=state,
                    problem=_safe_text(state.get("complaint")),
                    complaint_id=complaint_id,
                    causes=candidates,
                )
                zero_input_payload = _to_state_payload(zero_input)
                zero_result = deep_serialize(
                    _call_with_debug(
                        "ZeroEvidenceAgent.analyze",
                        _get_zero_evidence_agent().analyze,
                        zero_input,
                        context={
                            "node": "fishbone_prepare_selection",
                            "complaint_id": complaint_id,
                            "session_id": _safe_text(state.get("session_id")),
                        },
                    )
                )
                zero_output_payload = _to_state_payload(zero_result)
                selected = (zero_result.get("selected_root_cause") or {})
                recommended_cause_id = _safe_text(selected.get("cause_id"), None)
                if recommended_cause_id:
                    for cause in candidates:
                        cause["zero_evidence_recommended"] = (
                            _safe_text(cause.get("cause_id")) == recommended_cause_id
                        )
            message = (
                "No fishbone causes met 90%+ matched evidence. "
                "Zero-evidence ranking was generated; select exactly one cause to continue into Why analysis."
            )

        if not candidates:
            return {
                "status": "error",
                "phase": "error",
                "error": "Fishbone produced no causes for human selection",
                "node_log": [{"node": "fishbone_prepare_selection", "status": "error", "timestamp": _now()}],
                "updated_at": time.time(),
            }

        log_transition(complaint_id, "fishbone_validated", "awaiting_fishbone_selection", "hitl_pause")
        return {
            "status": "awaiting_human_review",
            "phase": "awaiting_fishbone_selection",
            "awaiting_human_review": True,
            "hitl_type": "fishbone",
            "next_action": "resume_fishbone_selection",
            "message": message,
            "fishbone_zero_evidence_input": zero_input_payload,
            "fishbone_zero_evidence_output": zero_output_payload,
            "fishbone_candidate_causes": candidates,
            "fishbone_recommended_cause_id": recommended_cause_id,
            "fishbone_zero_evidence_result": zero_result,
            "node_log": [{
                "node": "fishbone_prepare_selection",
                "status": "awaiting_input",
                "candidates": len(candidates),
                "timestamp": _now(),
            }],
            "timeline": [{
                "step": "fishbone_prepare_selection",
                "status": "awaiting_input",
                "candidates": len(candidates),
                "timestamp": _now(),
            }],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("fishbone_prepare_selection_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Fishbone candidate preparation failed: {exc}",
            "node_log": [{"node": "fishbone_prepare_selection", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def await_fishbone_selection_node(state: RCAV2GraphState) -> Dict[str, Any]:
    selected_id = _safe_text(state.get("fishbone_selected_cause_id"))
    candidates = state.get("fishbone_candidate_causes") or []

    if not selected_id:
        return {
            "status": "error",
            "phase": "error",
            "error": "selected_cause_id is required to resume fishbone selection",
            "node_log": [{"node": "await_fishbone_selection", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }

    selected = _select_cause_by_id(candidates, selected_id)
    if not selected:
        return {
            "status": "error",
            "phase": "error",
            "error": f"Selected fishbone cause_id '{selected_id}' is not present in candidate list",
            "node_log": [{"node": "await_fishbone_selection", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }

    return {
        "status": "running",
        "phase": "fishbone_selection_confirmed",
        "awaiting_human_review": False,
        "hitl_type": None,
        "next_action": None,
        "active_problem_text": _safe_text(selected.get("cause_text")),
        "message": "Fishbone selection accepted. Starting Why analysis.",
        "node_log": [{"node": "await_fishbone_selection", "status": "selected", "timestamp": _now()}],
        "timeline": [{
            "step": "fishbone_selection_confirmed",
            "selected_cause_id": selected_id,
            "selected_cause_text": _safe_text(selected.get("cause_text")),
            "timestamp": _now(),
        }],
        "audit_log": [{
            "time": time.time(),
            "action": "fishbone_cause_selected",
            "detail": selected_id,
        }],
        "updated_at": time.time(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# WHY NODES
# ══════════════════════════════════════════════════════════════════════════════

def why_question_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    question_session_id = _safe_text(state.get("question_agent_session_id"), complaint_id)
    depth = int(state.get("why_depth") or 0)
    problem = _safe_text(state.get("active_problem_text"), _safe_text(state.get("complaint")))

    try:
        question_mode = "continue"
        question_input_payload: Dict[str, Any]
        if depth == 0:
            start_input = StartWhyInput(
                complaint_id=question_session_id,
                complaint=problem,
                evidence=_safe_text(state.get("evidence")),
                sop=_safe_text(state.get("sop")),
            )
            question_mode = "start"
            question_input_payload = _to_state_payload(start_input)
            q_result = _call_with_debug(
                "WhyQuestionAgent.start",
                _get_question_agent().start,
                start_input,
                context={
                    "node": "why_question",
                    "complaint_id": complaint_id,
                    "session_id": _safe_text(state.get("session_id")),
                },
            )
        else:
            continue_input = ContinueWhyInput(
                complaint_id=question_session_id,
                answer=problem,
            )
            question_input_payload = _to_state_payload(continue_input)
            q_result = _call_with_debug(
                "WhyQuestionAgent.continue_chain",
                _get_question_agent().continue_chain,
                continue_input,
                context={
                    "node": "why_question",
                    "complaint_id": complaint_id,
                    "session_id": _safe_text(state.get("session_id")),
                },
            )

        question = _safe_text((deep_serialize(q_result) or {}).get("why_question"))
        if not question:
            question = f"Why did this occur: {problem}?"
        question_output_payload = _to_state_payload(q_result)

        next_depth = depth + 1
        return {
            "status": "running",
            "phase": "why_question_generated",
            "current_why_question": question,
            "why_depth": next_depth,
            "why_question_start_input": question_input_payload if question_mode == "start" else None,
            "why_question_continue_input": question_input_payload if question_mode == "continue" else None,
            "why_question_output": question_output_payload,
            "why_question_calls": [{
                "depth": next_depth,
                "mode": question_mode,
                "input": question_input_payload,
                "output": question_output_payload,
            }],
            "node_log": [{"node": "why_question", "status": "success", "depth": next_depth, "timestamp": _now()}],
            "timeline": [{
                "step": "why_question_generated",
                "depth": next_depth,
                "question": question,
                "timestamp": _now(),
            }],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("why_question_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Why question generation failed: {exc}",
            "node_log": [{"node": "why_question", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def why_generate_causes_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    depth = int(state.get("why_depth") or 0)
    question = _safe_text(state.get("current_why_question"))
    problem = _safe_text(state.get("active_problem_text"), _safe_text(state.get("complaint")))

    try:
        question_input = QuestionInput(
            question_id=f"{complaint_id}_why_{depth}",
            question=question,
            context=problem,
            evidence_context=_build_evidence_context(state),
        )
        fmea_path = state.get("fmea_document_path")
        if isinstance(fmea_path, str) and fmea_path and not os.path.isabs(fmea_path):
            fmea_path = os.path.abspath(fmea_path)
        if isinstance(fmea_path, str) and fmea_path and not os.path.exists(fmea_path):
            fmea_path = None

        cause_input_payload = _to_state_payload(question_input)
        cause_input_payload["fmea_document_path"] = fmea_path

        result = _call_with_debug(
            "CauseGenerationAgent.process_question",
            _get_cause_agent().process_question,
            question_input,
            fmea_path,
            context={
                "node": "why_generate_causes",
                "complaint_id": complaint_id,
                "session_id": _safe_text(state.get("session_id")),
            },
        )
        cause_output_payload = _to_state_payload(result)
        causes = [
            _normalized_cause(c, f"C-{idx + 1:03d}")
            for idx, c in enumerate((deep_serialize(result).get("causes") or []))
        ]
        if not causes:
            causes = _build_fallback_causes(problem)

        return {
            "phase": "why_causes_generated",
            "why_cause_generation_input": cause_input_payload,
            "why_cause_generation_output": cause_output_payload,
            "why_cause_generation_calls": [{
                "depth": depth,
                "input": cause_input_payload,
                "output": cause_output_payload,
            }],
            "why_current_causes": causes,
            "node_log": [{"node": "why_generate_causes", "status": "success", "count": len(causes), "timestamp": _now()}],
            "timeline": [{"step": "why_generate_causes", "depth": depth, "count": len(causes), "timestamp": _now()}],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("why_generate_causes_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Why cause generation failed: {exc}",
            "node_log": [{"node": "why_generate_causes", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def why_validate_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    question = _safe_text(state.get("current_why_question"))
    causes = state.get("why_current_causes") or []

    try:
        validation_input = _build_validation_input(state, question, causes)
        validation_input_payload = _to_state_payload(validation_input)
        validation_result = _call_with_debug(
            "ValidationAgent.validate_causes",
            _get_validation_agent().validate_causes,
            validation_input,
            context={
                "node": "why_validate",
                "complaint_id": complaint_id,
                "session_id": _safe_text(state.get("session_id")),
            },
        )
        validation_output_payload = _to_state_payload(validation_result)
        merged, validated, qualified = _merge_validation(causes, validation_result)

        return {
            "phase": "why_validated",
            "why_validation_input": validation_input_payload,
            "why_validation_output": validation_output_payload,
            "why_validation_calls": [{
                "depth": int(state.get("why_depth") or 0),
                "input": validation_input_payload,
                "output": validation_output_payload,
            }],
            "why_validated_causes": merged,
            "why_qualified_causes": qualified,
            "node_log": [{
                "node": "why_validate",
                "status": "success",
                "total": len(merged),
                "qualified": len(qualified),
                "timestamp": _now(),
            }],
            "timeline": [{
                "step": "why_validate",
                "depth": int(state.get("why_depth") or 0),
                "total": len(merged),
                "qualified": len(qualified),
                "timestamp": _now(),
            }],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("why_validate_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Why validation failed: {exc}",
            "node_log": [{"node": "why_validate", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


def why_prepare_decision_node(state: RCAV2GraphState) -> Dict[str, Any]:
    depth = int(state.get("why_depth") or 0)
    question = _safe_text(state.get("current_why_question"))
    causes = state.get("why_current_causes") or []
    validated = state.get("why_validated_causes") or []
    qualified = state.get("why_qualified_causes") or []

    iteration_snapshot = {
        "depth": depth,
        "input_problem": _safe_text(state.get("active_problem_text")),
        "question": question,
        "generated_causes": deep_serialize(causes),
        "validated_causes": deep_serialize(validated),
        "qualified_causes": deep_serialize(qualified),
    }

    if not qualified:
        return {
            "phase": "why_zero_evidence_pending",
            "status": "running",
            "why_requires_zero_evidence": True,
            "awaiting_human_review": False,
            "hitl_type": None,
            "next_action": None,
            "message": "No qualified causes in this Why level. Routing to zero-evidence selection.",
            "why_candidate_causes": [],
            "why_iterations": [iteration_snapshot],
            "node_log": [{"node": "why_prepare_decision", "status": "zero_evidence", "timestamp": _now()}],
            "updated_at": time.time(),
        }

    return {
        "phase": "awaiting_why_decision",
        "status": "awaiting_human_review",
        "why_requires_zero_evidence": False,
        "awaiting_human_review": True,
        "hitl_type": "why",
        "next_action": "resume_why_decision",
        "message": f"Select one qualified cause and choose continue or root_cause (depth={depth}).",
        "why_candidate_causes": qualified,
        "why_iterations": [iteration_snapshot],
        "node_log": [{
            "node": "why_prepare_decision",
            "status": "awaiting_input",
            "qualified": len(qualified),
            "timestamp": _now(),
        }],
        "updated_at": time.time(),
    }


def await_why_decision_node(state: RCAV2GraphState) -> Dict[str, Any]:
    selected_id = _safe_text(state.get("why_selected_cause_id"))
    decision = _safe_text(state.get("why_human_decision"), "").lower()
    candidates = state.get("why_candidate_causes") or []

    if decision not in ("continue", "root_cause"):
        return {
            "status": "error",
            "phase": "error",
            "error": "decision must be 'continue' or 'root_cause'",
            "node_log": [{"node": "await_why_decision", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }

    if not selected_id:
        return {
            "status": "error",
            "phase": "error",
            "error": "selected_cause_id is required for why decision",
            "node_log": [{"node": "await_why_decision", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }

    selected = _select_cause_by_id(candidates, selected_id)
    if not selected:
        return {
            "status": "error",
            "phase": "error",
            "error": f"Selected why cause_id '{selected_id}' is not present in candidate list",
            "node_log": [{"node": "await_why_decision", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }

    chain_entry = {
        "loop": int(state.get("why_depth") or 0),
        "question": _safe_text(state.get("current_why_question")),
        "selected_cause_id": selected_id,
        "selected_cause": _safe_text(selected.get("cause_text")),
        "confidence": _safe_float(selected.get("validation_confidence"), 0.0),
        "decision": decision,
        "human_approved": True,
    }

    if decision == "continue":
        return {
            "status": "running",
            "phase": "why_continue",
            "awaiting_human_review": False,
            "hitl_type": None,
            "next_action": None,
            "message": "Continuing to next Why level.",
            "active_problem_text": _safe_text(selected.get("cause_text")),
            "why_chain": [chain_entry],
            "why_candidate_causes": [],
            "why_selected_cause_id": None,
            "why_human_decision": None,
            "node_log": [{"node": "await_why_decision", "status": "continue", "timestamp": _now()}],
            "timeline": [{"step": "why_decision", "decision": "continue", "selected_cause_id": selected_id, "timestamp": _now()}],
            "updated_at": time.time(),
        }

    final_root = {
        **_normalized_cause(selected, selected_id),
        "reason": "Human confirmed root cause.",
        "confidence_score": _safe_float(selected.get("validation_confidence"), 0.0),
        "selection_path": "human_review",
    }

    return {
        "status": "completed",
        "phase": "completed",
        "awaiting_human_review": False,
        "hitl_type": None,
        "next_action": None,
        "message": "Root cause confirmed by user.",
        "final_root_cause": final_root,
        "stopping_reason": "human_approved_root_cause",
        "why_chain": [chain_entry],
        "node_log": [{"node": "await_why_decision", "status": "root_cause", "timestamp": _now()}],
        "timeline": [{"step": "why_decision", "decision": "root_cause", "selected_cause_id": selected_id, "timestamp": _now()}],
        "updated_at": time.time(),
    }


def why_zero_evidence_node(state: RCAV2GraphState) -> Dict[str, Any]:
    complaint_id = _safe_text(state.get("complaint_id"))
    problem = _safe_text(state.get("active_problem_text"), _safe_text(state.get("complaint")))
    causes = state.get("why_validated_causes") or state.get("why_current_causes") or []

    if not causes:
        causes = _build_fallback_causes(problem)

    try:
        zero_input = _build_zero_evidence_input(
            state=state,
            problem=problem,
            complaint_id=complaint_id,
            causes=causes,
        )
        zero_input_payload = _to_state_payload(zero_input)
        zero_result = deep_serialize(
            _call_with_debug(
                "ZeroEvidenceAgent.analyze",
                _get_zero_evidence_agent().analyze,
                zero_input,
                context={
                    "node": "why_zero_evidence",
                    "complaint_id": complaint_id,
                    "session_id": _safe_text(state.get("session_id")),
                },
            )
        )
        zero_output_payload = _to_state_payload(zero_result)
        selected = (zero_result.get("selected_root_cause") or {})
        selected_id = _safe_text(selected.get("cause_id"))
        selected_source = _select_cause_by_id(causes, selected_id) or causes[0]

        final_root = {
            **_normalized_cause(selected_source, _safe_text(selected_source.get("cause_id"), "ROOT-UNKNOWN")),
            "reason": _safe_text(selected.get("reason"), "Selected via zero-evidence criticality."),
            "confidence_score": _safe_float(zero_result.get("confidence"), 0.5),
            "selection_path": "zero_evidence_mode",
        }

        chain_entry = {
            "loop": int(state.get("why_depth") or 0),
            "question": _safe_text(state.get("current_why_question")),
            "selected_cause_id": _safe_text(final_root.get("cause_id")),
            "selected_cause": _safe_text(final_root.get("cause_text")),
            "confidence": _safe_float(final_root.get("confidence_score"), 0.0),
            "decision": "ai_flagged",
            "human_approved": False,
        }

        return {
            "status": "ai_flagged",
            "phase": "completed",
            "awaiting_human_review": False,
            "hitl_type": None,
            "next_action": None,
            "message": "No qualified causes in Why flow. Zero-evidence mode selected terminal root cause.",
            "why_zero_evidence_input": zero_input_payload,
            "why_zero_evidence_output": zero_output_payload,
            "final_root_cause": final_root,
            "ai_flagged": True,
            "stopping_reason": "no_validated_cause_zero_evidence",
            "why_zero_evidence_calls": [{
                "depth": int(state.get("why_depth") or 0),
                "input": zero_input_payload,
                "output": zero_output_payload,
            }],
            "why_chain": [chain_entry],
            "node_log": [{"node": "why_zero_evidence", "status": "success", "timestamp": _now()}],
            "timeline": [{"step": "why_zero_evidence", "selected_cause_id": final_root.get("cause_id"), "timestamp": _now()}],
            "updated_at": time.time(),
        }
    except Exception as exc:
        log_error("why_zero_evidence_node", str(exc), complaint_id)
        return {
            "status": "error",
            "phase": "error",
            "error": f"Why zero-evidence selection failed: {exc}",
            "node_log": [{"node": "why_zero_evidence", "status": "error", "timestamp": _now()}],
            "updated_at": time.time(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# NODE: finalize
# ══════════════════════════════════════════════════════════════════════════════

def finalize_node(state: RCAV2GraphState) -> Dict[str, Any]:
    now = time.time()
    execution_time = round(now - float(state.get("start_time") or now), 4)

    final_output = {
        "complaint_id": _safe_text(state.get("complaint_id")),
        "session_id": _safe_text(state.get("session_id")),
        "method": _safe_text(state.get("method")),
        "status": _safe_text(state.get("status"), "error"),
        "phase": _safe_text(state.get("phase"), "error"),
        "message": state.get("message"),
        "next_action": state.get("next_action"),
        "awaiting_human_review": bool(state.get("awaiting_human_review", False)),
        "hitl_type": state.get("hitl_type"),
        "ai_flagged": bool(state.get("ai_flagged", False)),
        "stopping_reason": state.get("stopping_reason"),
        "error": state.get("error"),
        "root_cause": deep_serialize(state.get("final_root_cause")),
        "fishbone": {
            "all_causes": deep_serialize(state.get("fishbone_all_causes") or []),
            "categorized_causes": deep_serialize(state.get("fishbone_categorized_causes") or []),
            "validated_causes": deep_serialize(state.get("fishbone_validated_causes") or []),
            "qualified_causes": deep_serialize(state.get("fishbone_qualified_causes") or []),
            "candidate_causes": deep_serialize(state.get("fishbone_candidate_causes") or []),
            "category_summary": deep_serialize(state.get("fishbone_category_summary") or {}),
            "zero_evidence_result": deep_serialize(state.get("fishbone_zero_evidence_result")),
            "recommended_cause_id": state.get("fishbone_recommended_cause_id"),
            "selected_cause_id": state.get("fishbone_selected_cause_id"),
        },
        "why": {
            "depth": int(state.get("why_depth") or 0),
            "current_question": state.get("current_why_question"),
            "current_causes": deep_serialize(state.get("why_current_causes") or []),
            "validated_causes": deep_serialize(state.get("why_validated_causes") or []),
            "qualified_causes": deep_serialize(state.get("why_qualified_causes") or []),
            "candidate_causes": deep_serialize(state.get("why_candidate_causes") or []),
            "why_chain": deep_serialize(state.get("why_chain") or []),
            "iterations": deep_serialize(state.get("why_iterations") or []),
        },
        "agent_payloads": {
            "fishbone": {
                "cause_generation_input": deep_serialize(state.get("fishbone_cause_generation_input")),
                "cause_generation_output": deep_serialize(state.get("fishbone_cause_generation_output")),
                "categorize_input": deep_serialize(state.get("fishbone_categorize_input")),
                "categorize_output": deep_serialize(state.get("fishbone_categorize_output")),
                "validation_input": deep_serialize(state.get("fishbone_validation_input")),
                "validation_output": deep_serialize(state.get("fishbone_validation_output")),
                "zero_evidence_input": deep_serialize(state.get("fishbone_zero_evidence_input")),
                "zero_evidence_output": deep_serialize(state.get("fishbone_zero_evidence_output")),
            },
            "why": {
                "question_start_input": deep_serialize(state.get("why_question_start_input")),
                "question_continue_input": deep_serialize(state.get("why_question_continue_input")),
                "question_output": deep_serialize(state.get("why_question_output")),
                "cause_generation_input": deep_serialize(state.get("why_cause_generation_input")),
                "cause_generation_output": deep_serialize(state.get("why_cause_generation_output")),
                "validation_input": deep_serialize(state.get("why_validation_input")),
                "validation_output": deep_serialize(state.get("why_validation_output")),
                "zero_evidence_input": deep_serialize(state.get("why_zero_evidence_input")),
                "zero_evidence_output": deep_serialize(state.get("why_zero_evidence_output")),
                "question_calls": deep_serialize(state.get("why_question_calls") or []),
                "cause_generation_calls": deep_serialize(state.get("why_cause_generation_calls") or []),
                "validation_calls": deep_serialize(state.get("why_validation_calls") or []),
                "zero_evidence_calls": deep_serialize(state.get("why_zero_evidence_calls") or []),
            },
        },
        "timeline": deep_serialize(state.get("timeline") or []),
        "node_log": deep_serialize(state.get("node_log") or []),
        "audit_log": deep_serialize(state.get("audit_log") or []),
        "updated_at": now,
        "execution_time_seconds": execution_time,
    }

    return {
        "final_output": final_output,
        "updated_at": now,
        "node_log": [{"node": "finalize", "status": "complete", "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING
# ══════════════════════════════════════════════════════════════════════════════

def route_after_initialize(state: RCAV2GraphState) -> str:
    if state.get("status") == "error":
        return "finalize"
    return "fishbone_generate_causes" if state.get("method") == "fishbone" else "why_question"


def route_after_fishbone_generate(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "fishbone_categorize"


def route_after_fishbone_categorize(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "fishbone_validate"


def route_after_fishbone_validate(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "fishbone_prepare_selection"


def route_after_fishbone_prepare(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "await_fishbone_selection"


def route_after_await_fishbone(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "why_question"


def route_after_why_question(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "why_generate_causes"


def route_after_why_generate(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "why_validate"


def route_after_why_validate(state: RCAV2GraphState) -> str:
    return "finalize" if state.get("status") == "error" else "why_prepare_decision"


def route_after_why_prepare(state: RCAV2GraphState) -> str:
    if state.get("status") == "error":
        return "finalize"
    if state.get("why_requires_zero_evidence"):
        return "why_zero_evidence"
    return "await_why_decision"


def route_after_await_why(state: RCAV2GraphState) -> str:
    if state.get("status") == "error":
        return "finalize"
    if state.get("status") == "running":
        return "why_question"
    return "finalize"


def route_after_why_zero(state: RCAV2GraphState) -> str:
    return "finalize"


def route_after_finalize(state: RCAV2GraphState) -> str:
    return END


# ══════════════════════════════════════════════════════════════════════════════
# BUILD GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def build_orchestrator_v2():
    graph = StateGraph(RCAV2GraphState)

    graph.add_node("initialize", _node_logging_wrapper("initialize", initialize_node))
    graph.add_node("fishbone_generate_causes", _node_logging_wrapper("fishbone_generate_causes", fishbone_generate_causes_node))
    graph.add_node("fishbone_categorize", _node_logging_wrapper("fishbone_categorize", fishbone_categorize_node))
    graph.add_node("fishbone_validate", _node_logging_wrapper("fishbone_validate", fishbone_validate_node))
    graph.add_node("fishbone_prepare_selection", _node_logging_wrapper("fishbone_prepare_selection", fishbone_prepare_selection_node))
    graph.add_node("await_fishbone_selection", _node_logging_wrapper("await_fishbone_selection", await_fishbone_selection_node))

    graph.add_node("why_question", _node_logging_wrapper("why_question", why_question_node))
    graph.add_node("why_generate_causes", _node_logging_wrapper("why_generate_causes", why_generate_causes_node))
    graph.add_node("why_validate", _node_logging_wrapper("why_validate", why_validate_node))
    graph.add_node("why_prepare_decision", _node_logging_wrapper("why_prepare_decision", why_prepare_decision_node))
    graph.add_node("await_why_decision", _node_logging_wrapper("await_why_decision", await_why_decision_node))
    graph.add_node("why_zero_evidence", _node_logging_wrapper("why_zero_evidence", why_zero_evidence_node))

    graph.add_node("finalize", _node_logging_wrapper("finalize", finalize_node))

    graph.add_edge(START, "initialize")

    graph.add_conditional_edges(
        "initialize",
        route_after_initialize,
        {
            "fishbone_generate_causes": "fishbone_generate_causes",
            "why_question": "why_question",
            "finalize": "finalize",
        },
    )

    graph.add_conditional_edges(
        "fishbone_generate_causes",
        route_after_fishbone_generate,
        {
            "fishbone_categorize": "fishbone_categorize",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "fishbone_categorize",
        route_after_fishbone_categorize,
        {
            "fishbone_validate": "fishbone_validate",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "fishbone_validate",
        route_after_fishbone_validate,
        {
            "fishbone_prepare_selection": "fishbone_prepare_selection",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "fishbone_prepare_selection",
        route_after_fishbone_prepare,
        {
            "await_fishbone_selection": "await_fishbone_selection",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "await_fishbone_selection",
        route_after_await_fishbone,
        {
            "why_question": "why_question",
            "finalize": "finalize",
        },
    )

    graph.add_conditional_edges(
        "why_question",
        route_after_why_question,
        {
            "why_generate_causes": "why_generate_causes",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "why_generate_causes",
        route_after_why_generate,
        {
            "why_validate": "why_validate",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "why_validate",
        route_after_why_validate,
        {
            "why_prepare_decision": "why_prepare_decision",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "why_prepare_decision",
        route_after_why_prepare,
        {
            "await_why_decision": "await_why_decision",
            "why_zero_evidence": "why_zero_evidence",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "await_why_decision",
        route_after_await_why,
        {
            "why_question": "why_question",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "why_zero_evidence",
        route_after_why_zero,
        {
            "finalize": "finalize",
        },
    )

    graph.add_conditional_edges("finalize", route_after_finalize, {END: END})

    checkpointer = RedisSaver(_REDIS_URL, ttl={"default_ttl": RCA_V2_SESSION_TTL_MINUTES})
    checkpointer.setup()

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["await_fishbone_selection", "await_why_decision"],
    )


# Lazy singleton — built on first request so Redis failures don't crash app import.
_orchestrator_graph_v2 = None


def get_orchestrator_graph_v2():
    """Return the compiled RCA v2 orchestrator graph, building it on first call."""
    global _orchestrator_graph_v2
    if _orchestrator_graph_v2 is None:
        _orchestrator_graph_v2 = build_orchestrator_v2()
    return _orchestrator_graph_v2
