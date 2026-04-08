"""
Why Analysis V2 Orchestrator.

Flow:
question -> causes -> validator -> loop_control

Branching after validation:
- validated causes > 1 -> ranking -> loop_control
- validated causes == 1 -> loop_control (skip ranking)
- validated causes == 0 -> zero_evidence_mode -> stop (ai_flagged)
"""

import os
import time
import datetime
import uuid
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.redis import RedisSaver

from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.cause_generation.schemas import QuestionInput
from Agents.loop_control.agent import LoopControlAgent
from Agents.loop_control.state import LoopControlInput, WhyChainItem
from Agents.question.agent import WhyQuestionAgent
from Agents.question.schemas import ContinueWhyInput, StartWhyInput
from Agents.ranking.agent import RankingAgent
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import GeneratedCause, ValidationInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent
from Agents.zero_evidence_agent.schemas import CauseInput as ZeroEvidenceCauseInput
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput

from .logger import (
    log_error,
    log_iteration,
    log_node_entry,
    log_node_exit,
    log_routing_decision,
)
from .state import WhyAnalysisV2State

try:
    from config.redis_config import REDIS_URL as _REDIS_URL
except Exception:
    _REDIS_URL = "redis://localhost:6379"

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_NODE_RETRIES = 2  # Agent call attempts per node before returning error state


_question_agent: Optional[WhyQuestionAgent] = None
_cause_agent: Optional[CauseGenerationAgent] = None
_validation_agent: Optional[ValidationAgent] = None
_ranking_agent: Optional[RankingAgent] = None
_zero_evidence_agent: Optional[ZeroEvidenceAgent] = None
_loop_control_agent: Optional[LoopControlAgent] = None


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


def _get_ranking_agent() -> RankingAgent:
    global _ranking_agent
    if _ranking_agent is None:
        _ranking_agent = RankingAgent()
    return _ranking_agent


def _get_zero_evidence_agent() -> ZeroEvidenceAgent:
    global _zero_evidence_agent
    if _zero_evidence_agent is None:
        _zero_evidence_agent = ZeroEvidenceAgent()
    return _zero_evidence_agent


def _get_loop_control_agent() -> LoopControlAgent:
    global _loop_control_agent
    if _loop_control_agent is None:
        _loop_control_agent = LoopControlAgent()
    return _loop_control_agent


def _now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Redis state reader (mirrors risk_analysis_orchestrator pattern) ────────────
try:
    import redis as _redis_lib
    _redis_client = _redis_lib.from_url(_REDIS_URL, decode_responses=False)
except Exception:
    _redis_client = None


def _read_state_from_redis(session_id: str):
    """
    Read latest checkpoint state for session_id directly from Redis.
    Uses the same pointer-based pattern as risk_analysis_orchestrator.
    Returns {"nodes_completed": [...], "state": {...}} or None.
    """
    if _redis_client is None:
        return None
    try:
        pattern = f"checkpoint_latest:{session_id}:*"
        ptr_keys = _redis_client.keys(pattern)
        if not ptr_keys:
            return None

        nodes_found: list = []
        merged_state: dict = {}

        for ptr_key in ptr_keys:
            ptr_key_str = ptr_key.decode("utf-8") if isinstance(ptr_key, bytes) else ptr_key
            parts = ptr_key_str.split(":")
            node_name = parts[2] if len(parts) > 2 else "unknown"
            nodes_found.append(node_name)

            ptr_val = _redis_client.get(ptr_key)
            if not ptr_val:
                continue
            checkpoint_key = ptr_val.decode("utf-8") if isinstance(ptr_val, bytes) else ptr_val

            try:
                doc = _redis_client.json().get(checkpoint_key)
                if doc and isinstance(doc, dict):
                    channel_values = doc.get("checkpoint", {}).get("channel_values", {})
                    if channel_values:
                        merged_state.update(channel_values)
            except Exception:
                pass

        return {"nodes_completed": sorted(set(nodes_found)), "state": merged_state}
    except Exception:
        return None


def deep_serialize(obj: Any) -> Any:
    """Recursively convert nested objects to JSON-safe primitives."""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [deep_serialize(v) for v in obj]
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return deep_serialize(obj.model_dump(mode="json"))
        except Exception:
            return deep_serialize(obj.model_dump())
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return deep_serialize(obj.dict())
        except Exception:
            return str(obj)
    return str(obj)


def _safe_text(value: Any, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _safe_int(value: Any, default: int = 5) -> int:
    try:
        parsed = int(value)
        if parsed < 1:
            return 1
        if parsed > 10:
            return 10
        return parsed
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.5) -> float:
    try:
        parsed = float(value)
        if parsed < 0.0:
            return 0.0
        if parsed > 1.0:
            return 1.0
        return parsed
    except Exception:
        return default


def _confidence_label_to_float(label: str, default: float = 0.5) -> float:
    mapping = {"LOW": 0.35, "MEDIUM": 0.6, "HIGH": 0.85}
    return mapping.get(_safe_text(label, "").upper(), default)


def _normalized_cause(cause: Dict[str, Any], fallback_id: str) -> Dict[str, Any]:
    return {
        "cause_id": _safe_text(cause.get("cause_id"), fallback_id),
        "cause_text": _safe_text(cause.get("cause_text"), "Unspecified cause description"),
        "process_step": _safe_text(cause.get("process_step"), "Unknown process step"),
        "failure_mode": _safe_text(cause.get("failure_mode"), "Unspecified failure mode"),
        "potential_effects": _safe_text(cause.get("potential_effects"), "Potential operational impact"),
        "severity": _safe_int(cause.get("severity"), 5),
        "occurrence": _safe_int(cause.get("occurrence"), 5),
        "detection": _safe_int(cause.get("detection"), 5),
        "current_controls": _safe_text(cause.get("current_controls"), "Not provided"),
        "source": _safe_text(cause.get("source"), "unknown"),
    }


def _build_root_cause(
    cause: Dict[str, Any],
    reason: str,
    confidence: float,
    selection_path: str,
) -> Dict[str, Any]:
    normalized = _normalized_cause(cause, "ROOT-UNKNOWN")
    normalized.update(
        {
            "reason": reason,
            "confidence_score": _safe_float(confidence, 0.5),
            "selection_path": selection_path,
        }
    )
    return normalized


def _build_iteration_output(
    state: WhyAnalysisV2State,
    branch: str,
    loop_decision: Optional[str] = None,
    loop_reasoning: Optional[str] = None,
) -> Dict[str, Any]:
    """Build complete per-iteration agent outputs for observability."""
    selected = state.get("current_selected_cause") or {}
    return {
        "loop": int(state.get("current_loop_count", 0)),
        "question": state.get("current_why_question"),
        "selected_cause_id": selected.get("cause_id"),
        "selected_cause": selected.get("cause_text"),
        "selected_confidence": _safe_float(state.get("current_cause_confidence"), 0.0),
        "branch": branch,
        "loop_decision": loop_decision,
        "loop_reasoning": loop_reasoning,
        "question_agent_input": deep_serialize(state.get("current_question_input") or {}),
        "question_agent_output": deep_serialize(state.get("current_question_result") or {}),
        "cause_generation_agent_input": deep_serialize(state.get("current_cause_generation_input") or {}),
        "cause_generation_agent_output": deep_serialize(state.get("current_cause_generation_result") or {}),
        "validation_agent_input": deep_serialize(state.get("current_validation_input") or {}),
        "validation_agent_output": deep_serialize(state.get("current_validation_result") or {}),
        "ranking_agent_input": deep_serialize(state.get("current_ranking_input") or {}),
        "ranking_agent_output": deep_serialize(state.get("current_ranking_result") or {}),
        "zero_evidence_agent_input": deep_serialize(state.get("current_zero_evidence_input") or {}),
        "zero_evidence_agent_output": deep_serialize(state.get("current_zero_evidence_result") or {}),
        "loop_control_agent_input": deep_serialize(state.get("current_loop_control_input") or {}),
        "loop_control_agent_output": deep_serialize(state.get("loop_control_result") or {}),
    }


def _build_fallback_causes(question: str) -> List[Dict[str, Any]]:
    """Build deterministic fallback causes when upstream generation returns empty."""
    question_text = _safe_text(question, "the observed issue")
    return [
        {
            "cause_id": "C001",
            "cause_text": f"System default override triggered during processing of: {question_text}",
            "process_step": "Application logic",
            "failure_mode": "Default value overwrite",
            "potential_effects": "Incorrect output values shown in generated records",
            "severity": 8,
            "occurrence": 5,
            "detection": 4,
            "current_controls": "Add rule-based validation before final record generation",
            "source": "Fallback_Generated",
        },
        {
            "cause_id": "C002",
            "cause_text": "Data mapping mismatch between prescription source and summary template fields",
            "process_step": "Data integration",
            "failure_mode": "Field mapping error",
            "potential_effects": "Critical values populated from stale or wrong source",
            "severity": 9,
            "occurrence": 4,
            "detection": 5,
            "current_controls": "Schema contract checks and end-to-end reconciliation tests",
            "source": "Fallback_Generated",
        },
    ]


def initialize_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("initialize", state)

    complaint = _safe_text(state.get("complaint"), "")
    complaint_id = _safe_text(state.get("complaint_id"), "")

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])

    if not complaint_id:
        errors.append({"node": "initialize", "error": "complaint_id is required", "timestamp": _now()})
        updates = {
            "status": "error",
            "error": "complaint_id is required",
            "stopping_reason": "invalid_input",
            "next_step": "finalize",
            "node_log": node_log,
            "errors": errors,
        }
        log_node_exit("initialize", updates)
        return updates

    if not complaint:
        errors.append({"node": "initialize", "error": "complaint is required", "timestamp": _now()})
        updates = {
            "status": "error",
            "error": "complaint is required",
            "stopping_reason": "invalid_input",
            "next_step": "finalize",
            "node_log": node_log,
            "errors": errors,
        }
        log_node_exit("initialize", updates)
        return updates

    fmea_path = state.get("fmea_document_path")
    has_fmea = bool(fmea_path and os.path.exists(fmea_path))
    mode = "FMEA_ITERATIVE" if has_fmea else "NO_FMEA_SINGLE_SHOT"

    node_log.append({"node": "initialize", "status": "success", "loop": 0, "timestamp": _now()})

    updates = {
        "has_fmea": has_fmea,
        "mode": mode,
        "max_loops": state.get("max_loops") or 10,
        "current_loop_count": 0,
        "current_why_question": None,
        "current_why_reasoning": None,
        "current_question_result": {},
        "current_question_input": {},
        "current_causes": [],
        "current_total_causes": 0,
        "current_fmea_matched": 0,
        "current_cause_generation_result": {},
        "current_cause_generation_input": {},
        "current_selected_cause": None,
        "current_cause_confidence": 0.0,
        "current_selection_path": "",
        "current_validation_result": {},
        "current_validation_input": {},
        "current_ranking_result": {},
        "current_ranking_input": {},
        "current_zero_evidence_result": {},
        "current_zero_evidence_input": {},
        "current_loop_control_input": {},
        "validated_causes_enriched": [],
        "validation_result": {},
        "ranking_result": {},
        "zero_evidence_result": {},
        "loop_control_result": {},
        "why_chain": [],
        "iteration_outputs": [],
        "final_root_cause": None,
        "ai_flagged": False,
        "manual_investigation_required": False,
        "status": "running",
        "error": None,
        "stopping_reason": None,
        "next_step": "generate_question",
        "node_log": node_log,
        "errors": errors,
    }
    log_routing_decision("initialize", "generate_question", f"mode={mode}")
    log_node_exit("initialize", updates)
    return updates


def generate_question_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("generate_question", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    current_loop_count = int(state.get("current_loop_count", 0))
    last_exc: Optional[Exception] = None

    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_question_agent()
            question_input_dump: Dict[str, Any] = {}

            if current_loop_count == 0:
                start_input = StartWhyInput(
                    complaint_id=state["complaint_id"],
                    complaint=state["complaint"],
                    evidence=state.get("evidence") or "",
                    sop=state.get("sop") or "",
                )
                question_input_dump = start_input.model_dump()
                result = agent.start(start_input)
            else:
                selected = state.get("current_selected_cause") or {}
                answer = _safe_text(selected.get("cause_text"), "Unknown cause")
                continue_input = ContinueWhyInput(
                    complaint_id=state["complaint_id"],
                    answer=answer,
                )
                question_input_dump = continue_input.model_dump()
                result = agent.continue_chain(continue_input)

            if result.get("error") or not result.get("why_question"):
                error_message = _safe_text(result.get("error"), "Question generation failed")
                errors.append({"node": "generate_question", "error": error_message, "timestamp": _now()})
                updates = {
                    "status": "error",
                    "error": error_message,
                    "stopping_reason": "question_generation_failed",
                    "next_step": "finalize",
                    "node_log": node_log,
                    "errors": errors,
                }
                log_error("generate_question", error_message)
                log_node_exit("generate_question", updates)
                return updates

            node_log.append({"node": "generate_question", "status": "success", "loop": current_loop_count, "timestamp": _now()})
            updates = {
                "current_loop_count": current_loop_count + 1,
                "current_why_question": result.get("why_question"),
                "current_why_reasoning": result.get("reasoning") or "",
                "current_question_input": deep_serialize(question_input_dump),
                "current_question_result": deep_serialize(result),
                "next_step": "generate_causes",
                "node_log": node_log,
                "errors": errors,
            }
            log_routing_decision("generate_question", "generate_causes", "question generated")
            log_node_exit("generate_question", updates)
            return updates

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("generate_question", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    message = f"Question agent failure after {MAX_NODE_RETRIES} attempts: {last_exc}"
    errors.append({"node": "generate_question", "error": message, "timestamp": _now()})
    updates = {
        "status": "error",
        "error": message,
        "stopping_reason": "question_generation_exception",
        "next_step": "finalize",
        "node_log": node_log,
        "errors": errors,
    }
    log_error("generate_question", message)
    log_node_exit("generate_question", updates)
    return updates


def generate_causes_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("generate_causes", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    last_exc: Optional[Exception] = None

    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_cause_agent()

            context_value = state.get("complaint") or ""
            if int(state.get("current_loop_count", 0)) > 1:
                selected = state.get("current_selected_cause") or {}
                context_value = _safe_text(selected.get("cause_text"), context_value)

            # Build a rich evidence_context so the cause-generation LLM has
            # all available evidence (same optional fields the user passed in).
            evidence_ctx: Dict[str, Any] = {"evidence": state.get("evidence") or ""}
            for _ev_field in (
                "sop",
                "logs",
                "reports",
                "process_data",
                "historical_capa",
                "policies",
                "investigation_records",
                "supporting_system_information",
            ):
                _val = state.get(_ev_field)
                if _val:
                    evidence_ctx[_ev_field] = _val

            question_input = QuestionInput(
                question_id=f"{state['complaint_id']}",
                question=state["current_why_question"],
                context=context_value,
                evidence_context=evidence_ctx,
            )

            fmea_path = state.get("fmea_document_path") if state.get("has_fmea") else None
            cause_generation_input_dump = {
                "question_input": question_input.model_dump(),
                "fmea_document_path": fmea_path,
            }
            result = agent.process_question(question_input=question_input, fmea_document_path=fmea_path)

            causes_raw = result.get("causes") or []
            causes = [_normalized_cause(c, f"C-{idx + 1:03d}") for idx, c in enumerate(causes_raw)]

            # If FMEA context is present but returns no causes, retry in LLM-only mode.
            if not causes and state.get("has_fmea"):
                log_routing_decision(
                    "generate_causes",
                    "generate_causes",
                    "FMEA-based retrieval returned 0 causes. Retrying in LLM-only mode.",
                )
                retry_result = agent.process_question(question_input=question_input, fmea_document_path=None)
                retry_causes_raw = retry_result.get("causes") or []
                if retry_causes_raw:
                    causes = [_normalized_cause(c, f"C-{idx + 1:03d}") for idx, c in enumerate(retry_causes_raw)]
                    result = retry_result

            # Final safety net to keep orchestration moving through validation/branch logic.
            if not causes:
                causes = _build_fallback_causes(state.get("current_why_question") or "")
                result = {
                    **result,
                    "matched_entries": 0,
                    "notes": "Generated deterministic fallback causes after empty upstream output.",
                }

            node_log.append({"node": "generate_causes", "status": "success", "loop": int(state.get("current_loop_count", 0)), "timestamp": _now()})
            updates: Dict[str, Any] = {
                "current_causes": causes,
                "current_total_causes": len(causes),
                "current_fmea_matched": int(result.get("matched_entries") or 0),
                "current_cause_generation_input": deep_serialize(cause_generation_input_dump),
                "current_cause_generation_result": deep_serialize(result),
                "next_step": "validate_causes",
                "node_log": node_log,
                "errors": errors,
            }
            log_routing_decision("generate_causes", "validate_causes", f"causes={len(causes)}")
            log_node_exit("generate_causes", updates)
            return updates

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("generate_causes", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    message = f"Cause generation failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    errors.append({"node": "generate_causes", "error": message, "timestamp": _now()})
    updates = {
        "status": "error",
        "error": message,
        "stopping_reason": "cause_generation_exception",
        "next_step": "finalize",
        "node_log": node_log,
        "errors": errors,
    }
    log_error("generate_causes", message)
    log_node_exit("generate_causes", updates)
    return updates


def validate_causes_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("validate_causes", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    last_exc: Optional[Exception] = None

    causes = state.get("current_causes") or []
    if not causes:
        errors.append({"node": "validate_causes", "error": "Validation called with empty cause list", "timestamp": _now()})
        updates = {
            "status": "error",
            "error": "Validation called with empty cause list",
            "stopping_reason": "validation_input_error",
            "next_step": "finalize",
            "node_log": node_log,
            "errors": errors,
        }
        log_node_exit("validate_causes", updates)
        return updates

    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_validation_agent()

            generated_causes: List[GeneratedCause] = []
            for i, cause in enumerate(causes):
                generated_causes.append(
                    GeneratedCause(
                        cause_id=_safe_text(cause.get("cause_id"), f"C-{i + 1:03d}"),
                        cause_text=_safe_text(cause.get("cause_text"), "Unspecified cause description"),
                        process_step=cause.get("process_step"),
                        failure_mode=cause.get("failure_mode"),
                        potential_effects=cause.get("potential_effects"),
                        severity=int(cause.get("severity")) if cause.get("severity") is not None else None,
                        occurrence=int(cause.get("occurrence")) if cause.get("occurrence") is not None else None,
                        detection=int(cause.get("detection")) if cause.get("detection") is not None else None,
                        current_controls=cause.get("current_controls"),
                        source=_safe_text(cause.get("source"), "Generated"),
                    )
                )

            validation_input = ValidationInput(
                complaint_id=state.get("complaint_id"),
                question=state.get("current_why_question"),
                generated_causes=generated_causes,
                complaint_description=state.get("complaint") or "",
                logs=state.get("logs"),
                reports=state.get("reports"),
                process_data=state.get("process_data"),
                historical_capa=state.get("historical_capa"),
                policies=state.get("policies"),
                sop=state.get("sop"),
                investigation_records=state.get("investigation_records"),
                supporting_system_information=state.get("supporting_system_information"),
                investigation_evidence={
                    "evidence_text": state.get("evidence") or "",
                    "evidence_files": state.get("evidence_files") or [],
                },
            )

            validation_input_dump = validation_input.model_dump(mode="json")
            validation_result = deep_serialize(agent.validate_causes(validation_input))
            valid_items = validation_result.get("validated_causes") or []
            cause_lookup = {c["cause_id"]: c for c in causes}

            enriched_validated: List[Dict[str, Any]] = []
            for item in valid_items:
                cid = _safe_text(item.get("cause_id"), "")
                base = _normalized_cause(cause_lookup.get(cid, {}), cid or "C-UNKNOWN")
                enriched_validated.append(
                    {
                        **base,
                        "evidence_match_status": _safe_text(item.get("evidence_match_status"), "unknown"),
                        "supporting_evidence_references": item.get("supporting_evidence_references") or [],
                        "validation_confidence": _safe_float(item.get("confidence"), 0.5),
                        "validation_rationale": _safe_text(item.get("rationale"), "No rationale provided"),
                    }
                )

            node_log.append({"node": "validate_causes", "status": "success", "loop": int(state.get("current_loop_count", 0)), "timestamp": _now()})
            updates: Dict[str, Any] = {
                "validation_result": validation_result,
                "current_validation_input": deep_serialize(validation_input_dump),
                "current_validation_result": validation_result,
                "validated_causes_enriched": enriched_validated,
                "node_log": node_log,
                "errors": errors,
            }

            valid_count = len(enriched_validated)
            if valid_count == 0:
                updates["next_step"] = "zero_evidence_mode"
                log_routing_decision("validate_causes", "zero_evidence_mode", "no validated causes")
            elif valid_count == 1:
                selected = enriched_validated[0]
                updates.update(
                    {
                        "current_selected_cause": selected,
                        "current_cause_confidence": _safe_float(selected.get("validation_confidence"), 0.5),
                        "current_selection_path": "single_validated_no_ranking",
                        "next_step": "loop_control",
                    }
                )
                log_routing_decision("validate_causes", "loop_control", "single validated cause")
            else:
                updates["next_step"] = "rank_causes"
                log_routing_decision("validate_causes", "rank_causes", f"validated causes={valid_count}")

            log_node_exit("validate_causes", updates)
            return updates

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("validate_causes", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    message = f"Validation failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    errors.append({"node": "validate_causes", "error": message, "timestamp": _now()})
    updates = {
        "status": "error",
        "error": message,
        "stopping_reason": "validation_exception",
        "next_step": "finalize",
        "node_log": node_log,
        "errors": errors,
    }
    log_error("validate_causes", message)
    log_node_exit("validate_causes", updates)
    return updates


def rank_causes_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("rank_causes", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    last_exc: Optional[Exception] = None

    validated = state.get("validated_causes_enriched") or []
    if len(validated) < 2:
        errors.append({"node": "rank_causes", "error": "Ranking node requires at least two validated causes", "timestamp": _now()})
        updates = {
            "status": "error",
            "error": "Ranking node requires at least two validated causes",
            "stopping_reason": "ranking_input_error",
            "next_step": "finalize",
            "node_log": node_log,
            "errors": errors,
        }
        log_node_exit("rank_causes", updates)
        return updates

    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_ranking_agent()

            ranking_causes = []
            for idx, cause in enumerate(validated):
                normalized = _normalized_cause(cause, f"RC-{idx + 1:03d}")
                ranking_causes.append(
                    {
                        "cause_id": normalized["cause_id"],
                        "cause_text": normalized["cause_text"],
                        "process_step": normalized["process_step"],
                        "failure_mode": normalized["failure_mode"],
                        "potential_effects": normalized["potential_effects"],
                        "severity": normalized["severity"],
                        "occurrence": normalized["occurrence"],
                        "detection": normalized["detection"],
                        "metadata": {
                            "validation_confidence": _safe_float(cause.get("validation_confidence"), 0.5),
                            "evidence_match_status": cause.get("evidence_match_status"),
                        },
                    }
                )

            ranking_config = {
                "domain": "manufacturing",
                "evidence_context": "pharmaceutical CAPA investigation evidence and document records",
                "mechanism_context": _safe_text(state.get("sop"), "FMEA technical failure mode analysis"),
                "proximity_context": "root cause causal chain analysis for recurring defect prevention",
            }
            ranking_input_dump = {
                "causes": ranking_causes,
                "config": ranking_config,
            }
            ranking_output = agent.rank_causes(causes=ranking_causes, config=ranking_config)
            ranking_dump = deep_serialize(ranking_output)

            selected_id = _safe_text(ranking_dump.get("selected_root_cause"), "")
            ranked_causes = ranking_dump.get("ranked_causes") or []
            ranked_top = ranked_causes[0] if ranked_causes else {}

            selected = None
            for cause in validated:
                if cause.get("cause_id") == selected_id:
                    selected = {**cause}
                    break
            if selected is None:
                selected = {**validated[0]}

            selected["ranking_rcps_score"] = ranked_top.get("rcps_score")
            selected["ranking_risk_level"] = ranked_top.get("risk_level")

            confidence = _safe_float(
                min(
                    _safe_float(selected.get("validation_confidence"), 0.6),
                    _safe_float(ranked_top.get("confidence"), _safe_float(selected.get("validation_confidence"), 0.6)),
                ),
                _safe_float(selected.get("validation_confidence"), 0.6),
            )

            node_log.append({"node": "rank_causes", "status": "success", "loop": int(state.get("current_loop_count", 0)), "timestamp": _now()})
            updates = {
                "ranking_result": ranking_dump,
                "current_ranking_input": deep_serialize(ranking_input_dump),
                "current_ranking_result": ranking_dump,
                "current_selected_cause": selected,
                "current_cause_confidence": confidence,
                "current_selection_path": "ranking_after_multi_validation",
                "next_step": "loop_control",
                "node_log": node_log,
                "errors": errors,
            }
            log_routing_decision("rank_causes", "loop_control", f"selected={selected.get('cause_id')}")
            log_node_exit("rank_causes", updates)
            return updates

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("rank_causes", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    message = f"Ranking failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    errors.append({"node": "rank_causes", "error": message, "timestamp": _now()})
    updates = {
        "status": "error",
        "error": message,
        "stopping_reason": "ranking_exception",
        "next_step": "finalize",
        "node_log": node_log,
        "errors": errors,
    }
    log_error("rank_causes", message)
    log_node_exit("rank_causes", updates)
    return updates


def zero_evidence_mode_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("zero_evidence_mode", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    last_exc: Optional[Exception] = None

    causes = state.get("current_causes") or []
    if not causes:
        errors.append({"node": "zero_evidence_mode", "error": "Zero evidence mode could not run because cause list is empty", "timestamp": _now()})
        updates = {
            "status": "error",
            "error": "Zero evidence mode could not run because cause list is empty",
            "stopping_reason": "zero_evidence_input_error",
            "next_step": "finalize",
            "node_log": node_log,
            "errors": errors,
        }
        log_node_exit("zero_evidence_mode", updates)
        return updates

    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_zero_evidence_agent()

            ze_causes = [
                ZeroEvidenceCauseInput(
                    cause_id=_safe_text(c.get("cause_id"), f"ZE-{idx + 1:03d}"),
                    cause_text=_safe_text(c.get("cause_text"), "Unspecified cause description"),
                    process_step=_safe_text(c.get("process_step"), "Unknown process step"),
                    failure_mode=_safe_text(c.get("failure_mode"), "Unspecified failure mode"),
                    potential_effects=c.get("potential_effects"),
                    severity=_safe_int(c.get("severity"), 5),
                    occurrence=_safe_int(c.get("occurrence"), 5),
                    detection=_safe_int(c.get("detection"), 5),
                    current_controls=_safe_text(c.get("current_controls"), "Not provided"),
                    source=_safe_text(c.get("source"), "unknown"),
                )
                for idx, c in enumerate(causes)
            ]

            ze_input = ZeroEvidenceInput(
                question_id=f"{state['complaint_id']}",
                question=state.get("current_why_question") or "",
                causes=ze_causes,
                total_causes=len(ze_causes),
            )

            zero_evidence_input_dump = ze_input.model_dump(mode="json")
            ze_result = deep_serialize(agent.analyze(ze_input))
            selected = ze_result.get("selected_root_cause") or {}

            selected_cause_id = _safe_text(selected.get("cause_id"), "")
            selected_source = None
            for cause in causes:
                if cause.get("cause_id") == selected_cause_id:
                    selected_source = cause
                    break

            if selected_source is None:
                selected_source = causes[0]

            reason = _safe_text(
                selected.get("reason"),
                "No validated causes found. Zero evidence mode selected highest criticality cause.",
            )
            confidence = _confidence_label_to_float(ze_result.get("confidence"), 0.6)

            final_root = _build_root_cause(
                selected_source,
                reason=reason,
                confidence=confidence,
                selection_path="zero_evidence_mode",
            )

            node_log.append({"node": "zero_evidence_mode", "status": "success", "loop": int(state.get("current_loop_count", 0)), "timestamp": _now()})
            updates = {
                "zero_evidence_result": ze_result,
                "current_zero_evidence_input": deep_serialize(zero_evidence_input_dump),
                "current_zero_evidence_result": ze_result,
                "current_selected_cause": selected_source,
                "current_cause_confidence": confidence,
                "current_selection_path": "zero_evidence_mode",
                "final_root_cause": final_root,
                "status": "ai_flagged",
                "ai_flagged": True,
                "stopping_reason": "no_validated_cause_zero_evidence",
                "next_step": "finalize",
                "node_log": node_log,
                "errors": errors,
            }
            iteration_outputs = list(state.get("iteration_outputs") or [])
            iteration_outputs.append(_build_iteration_output({**state, **updates}, branch="zero_evidence_terminal"))
            updates["iteration_outputs"] = iteration_outputs
            log_routing_decision("zero_evidence_mode", "finalize", "ai_flagged terminal path")
            log_node_exit("zero_evidence_mode", updates)
            return updates

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("zero_evidence_mode", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    message = f"Zero evidence mode failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    errors.append({"node": "zero_evidence_mode", "error": message, "timestamp": _now()})
    updates = {
        "status": "error",
        "error": message,
        "stopping_reason": "zero_evidence_exception",
        "next_step": "finalize",
        "node_log": node_log,
        "errors": errors,
    }
    log_error("zero_evidence_mode", message)
    log_node_exit("zero_evidence_mode", updates)
    return updates


def loop_control_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("loop_control", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    last_exc: Optional[Exception] = None

    selected = state.get("current_selected_cause")
    if not selected:
        errors.append({"node": "loop_control", "error": "Loop control requires a selected cause", "timestamp": _now()})
        updates = {
            "status": "error",
            "error": "Loop control requires a selected cause",
            "stopping_reason": "loop_control_input_error",
            "next_step": "finalize",
            "node_log": node_log,
            "errors": errors,
        }
        log_node_exit("loop_control", updates)
        return updates

    loop_number = int(state.get("current_loop_count", 0))
    max_loops = int(state.get("max_loops", 10))
    confidence = _safe_float(state.get("current_cause_confidence"), 0.5)
    selection_path = _safe_text(state.get("current_selection_path"), "unknown")

    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_loop_control_agent()

            current_entry = {
                "loop": loop_number,
                "question": _safe_text(state.get("current_why_question"), ""),
                "selected_cause": _safe_text(selected.get("cause_text"), ""),
                "selected_cause_id": _safe_text(selected.get("cause_id"), ""),
                "confidence": confidence,
                "selection_path": selection_path,
                "loop_decision": None,
                "loop_reasoning": None,
            }

            chain_history = list(state.get("why_chain") or [])
            chain_history.append(current_entry)

            payload_chain = [
                WhyChainItem(
                    loop=max(1, int(item.get("loop", idx + 1))),
                    question=_safe_text(item.get("question"), "unknown question"),
                    cause=_safe_text(item.get("selected_cause"), "unknown cause"),
                    confidence=_safe_float(item.get("confidence"), 0.5),
                )
                for idx, item in enumerate(chain_history)
            ]

            loop_input = LoopControlInput(
                incident_description=_safe_text(state.get("complaint"), ""),
                current_loop_count=loop_number,
                max_loops=max_loops,
                current_top_cause=_safe_text(selected.get("cause_text"), "unknown cause"),
                current_cause_confidence=confidence,
                fmea_document_path=state.get("fmea_document_path"),
                full_why_chain=payload_chain,
            )
            loop_input_dump = deep_serialize(loop_input)

            loop_result = deep_serialize(agent.evaluate(loop_input))
            decision = _safe_text(loop_result.get("decision"), "STOP_DEGRADED")
            reasoning = _safe_text(loop_result.get("reasoning"), "No reasoning provided")

            chain_history[-1]["loop_decision"] = decision
            chain_history[-1]["loop_reasoning"] = reasoning

            node_log.append({"node": "loop_control", "status": "success", "loop": loop_number, "timestamp": _now()})
            updates: Dict[str, Any] = {
                "why_chain": chain_history,
                "current_loop_control_input": loop_input_dump,
                "loop_control_result": loop_result,
                "node_log": node_log,
                "errors": errors,
            }

            iteration_outputs = list(state.get("iteration_outputs") or [])
            branch = "single_validated_no_ranking" if selection_path == "single_validated_no_ranking" else "ranking_after_multi_validation"
            iteration_outputs.append(
                _build_iteration_output(
                    {**state, **updates},
                    branch=branch,
                    loop_decision=decision,
                    loop_reasoning=reasoning,
                )
            )
            updates["iteration_outputs"] = iteration_outputs

            log_iteration(
                loop=loop_number,
                question=current_entry["question"],
                selected_cause=current_entry["selected_cause"],
                confidence=confidence,
            )

            if decision == "STOP_ROOT_FOUND":
                updates.update(
                    {
                        "final_root_cause": _build_root_cause(
                            selected,
                            reason=f"Loop control confirmed root cause: {reasoning}",
                            confidence=confidence,
                            selection_path=selection_path,
                        ),
                        "status": "completed",
                        "stopping_reason": "root_cause_confirmed",
                        "next_step": "finalize",
                    }
                )
                log_routing_decision("loop_control", "finalize", "STOP_ROOT_FOUND")
            elif decision == "STOP_DEGRADED":
                updates.update(
                    {
                        "status": "stopped_degraded",
                        "manual_investigation_required": True,
                        "stopping_reason": "loop_degraded_manual_review_required",
                        "next_step": "finalize",
                    }
                )
                log_routing_decision("loop_control", "finalize", "STOP_DEGRADED")
            else:
                if loop_number >= max_loops:
                    updates.update(
                        {
                            "status": "stopped_max_loops",
                            "manual_investigation_required": True,
                            "final_root_cause": _build_root_cause(
                                selected,
                                reason="Max loops reached before root confirmation. Escalate to manual investigation.",
                                confidence=confidence,
                                selection_path="max_loops_fallback",
                            ),
                            "stopping_reason": "max_loops_reached",
                            "next_step": "finalize",
                        }
                    )
                    log_routing_decision("loop_control", "finalize", "max loops reached")
                else:
                    updates["next_step"] = "generate_question"
                    log_routing_decision("loop_control", "generate_question", "LOOP")

            log_node_exit("loop_control", updates)
            return updates

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("loop_control", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    message = f"Loop control failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    errors.append({"node": "loop_control", "error": message, "timestamp": _now()})
    updates = {
        "status": "error",
        "error": message,
        "stopping_reason": "loop_control_exception",
        "next_step": "finalize",
        "node_log": node_log,
        "errors": errors,
    }
    log_error("loop_control", message)
    log_node_exit("loop_control", updates)
    return updates


def finalize_node(state: WhyAnalysisV2State) -> Dict[str, Any]:
    log_node_entry("finalize", state)

    node_log = list(state.get("node_log") or [])
    errors = list(state.get("errors") or [])
    execution_time = round(time.time() - float(state.get("start_time") or time.time()), 4)
    status = _safe_text(state.get("status"), "error")

    node_log.append({"node": "finalize", "status": "success", "loop": int(state.get("current_loop_count", 0)), "timestamp": _now()})

    final_output = {
        "complaint_id": state.get("complaint_id"),
        "session_id": state.get("session_id"),
        "status": status,
        "mode": state.get("mode", "NO_FMEA_SINGLE_SHOT"),
        "analysis_depth": int(state.get("current_loop_count", 0)),
        "max_loops": int(state.get("max_loops", 10)),
        "ai_flagged": bool(state.get("ai_flagged", False)),
        "manual_investigation_required": bool(state.get("manual_investigation_required", False)),
        "stopping_reason": state.get("stopping_reason"),
        "root_cause": state.get("final_root_cause"),
        "why_chain": state.get("why_chain", []),
        "iteration_outputs": state.get("iteration_outputs", []),
        "validation_summary": {
            "total_input_causes": (state.get("validation_result") or {}).get("total_input_causes", 0),
            "total_validated_causes": (state.get("validation_result") or {}).get("total_validated_causes", 0),
            "overall_confidence": (state.get("validation_result") or {}).get("overall_confidence"),
        },
        "loop_control_summary": {
            "decision": (state.get("loop_control_result") or {}).get("decision"),
            "reasoning": (state.get("loop_control_result") or {}).get("reasoning"),
            "next_step": (state.get("loop_control_result") or {}).get("next_step"),
        },
        "execution_time_seconds": execution_time,
        "error": state.get("error"),
        "node_log": node_log,
        "errors": errors,
    }

    if status == "completed" and not final_output["root_cause"]:
        final_output["status"] = "error"
        final_output["error"] = final_output["error"] or "Completed status set without final root cause"
        final_output["stopping_reason"] = final_output.get("stopping_reason") or "inconsistent_final_state"

    updates = {
        "final_output": deep_serialize(final_output),
        "node_log": node_log,
        "errors": errors,
        "next_step": END,
    }

    log_routing_decision("finalize", "END", f"status={final_output['status']}")
    log_node_exit("finalize", updates)
    return updates


def route_from_node(state: WhyAnalysisV2State) -> str:
    next_step = state.get("next_step", END)
    if next_step in (None, "end"):
        return END
    return next_step


def build_orchestrator_graph():
    workflow = StateGraph(WhyAnalysisV2State)

    workflow.add_node("initialize", initialize_node)
    workflow.add_node("generate_question", generate_question_node)
    workflow.add_node("generate_causes", generate_causes_node)
    workflow.add_node("validate_causes", validate_causes_node)
    workflow.add_node("rank_causes", rank_causes_node)
    workflow.add_node("zero_evidence_mode", zero_evidence_mode_node)
    workflow.add_node("loop_control", loop_control_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "generate_question")

    workflow.add_conditional_edges("generate_question", route_from_node)
    workflow.add_conditional_edges("generate_causes", route_from_node)
    workflow.add_conditional_edges("validate_causes", route_from_node)
    workflow.add_conditional_edges("rank_causes", route_from_node)
    workflow.add_conditional_edges("zero_evidence_mode", route_from_node)
    workflow.add_conditional_edges("loop_control", route_from_node)
    workflow.add_conditional_edges("finalize", route_from_node)

    try:
        checkpointer = RedisSaver(_REDIS_URL)
        return workflow.compile(checkpointer=checkpointer)
    except Exception:
        # Fall back to no checkpointer if Redis is unavailable at startup
        return workflow.compile()


orchestrator_graph = build_orchestrator_graph()
