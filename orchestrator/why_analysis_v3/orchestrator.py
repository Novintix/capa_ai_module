"""
why_analysis_v3/orchestrator.py

Why Analysis V3 Orchestrator

Simplified Flow:
    START
      ↓
    initialize
      ↓
    generate_question (Question Agent)
      ↓
    generate_causes (Cause Generation Agent)
      ↓
    validate_causes (Validation Agent)
      ├─ 0 causes → zero_evidence_mode → finalize → END (ai_flagged)
      └─ 1+ causes → human_review (PAUSED) → finalize → END (completed)

Key Principles (following risk_analysis_orchestrator_service):
  1. Payload building in separate payloads.py
  2. deep_serialize() for all agent results
  3. Proper tracking IDs (complaint_id, session_id)
  4. Complete context passing
  5. Redis checkpointing
  6. Node-based routing (no routing inside nodes)
"""

import os
import time
import datetime
import uuid
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph, START
from langgraph.checkpoint.redis import RedisSaver

from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.cause_generation.schemas import QuestionInput
from Agents.question.agent import WhyQuestionAgent
from Agents.question.schemas import ContinueWhyInput, StartWhyInput
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import GeneratedCause, ValidationInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent
from Agents.zero_evidence_agent.schemas import CauseInput as ZeroEvidenceCauseInput
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput

from .logger import log_error, log_node_entry, log_node_exit
from .state import WhyAnalysisV3State
from .payloads import build_all_payloads

try:
    from config.redis_config import REDIS_URL as _REDIS_URL
except Exception:
    _REDIS_URL = "redis://localhost:6379"

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

MAX_NODE_RETRIES = 2

# ══════════════════════════════════════════════════════════════════════════════
# REDIS
# ══════════════════════════════════════════════════════════════════════════════

try:
    import redis as _redis_lib
    redis_client = _redis_lib.from_url(_REDIS_URL, decode_responses=False)
except Exception:
    redis_client = None


def _read_state_from_redis(session_id: str):
    """
    Read latest checkpoint state for session_id from Redis.
    Uses the same pointer-based pattern as risk_analysis_orchestrator.
    Returns {"nodes_completed": [...], "state": {...}} or None.
    """
    if redis_client is None:
        return None
    try:
        pattern = f"checkpoint_latest:{session_id}:*"
        ptr_keys = redis_client.keys(pattern)
        if not ptr_keys:
            return None

        nodes_found: list = []
        merged_state: dict = {}

        for ptr_key in ptr_keys:
            ptr_key_str = ptr_key.decode("utf-8") if isinstance(ptr_key, bytes) else ptr_key
            parts = ptr_key_str.split(":")
            node_name = parts[2] if len(parts) > 2 else "unknown"
            nodes_found.append(node_name)

            ptr_val = redis_client.get(ptr_key)
            if not ptr_val:
                continue
            checkpoint_key = ptr_val.decode("utf-8") if isinstance(ptr_val, bytes) else ptr_val

            try:
                doc = redis_client.json().get(checkpoint_key)
                if doc and isinstance(doc, dict):
                    channel_values = doc.get("checkpoint", {}).get("channel_values", {})
                    if channel_values:
                        merged_state.update(channel_values)
            except Exception:
                pass

        return {"nodes_completed": sorted(set(nodes_found)), "state": merged_state}
    except Exception:
        return None



# ══════════════════════════════════════════════════════════════════════════════
# SERIALIZATION UTILITY
# Same pattern as risk_analysis_orchestrator_service
# ══════════════════════════════════════════════════════════════════════════════

def deep_serialize(obj: Any) -> Any:
    """
    Recursively converts any object to a JSON-serializable form.
    Applied to EVERY agent result before writing to state.
    """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            dumped = obj.model_dump(mode="json")
        except Exception:
            try:
                dumped = obj.model_dump()
            except Exception:
                return str(obj)
        return deep_serialize(dumped)
    
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            dumped = obj.dict()
            return deep_serialize(dumped)
        except Exception:
            pass
    
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [deep_serialize(v) for v in obj]
    
    return obj


def _now() -> str:
    """Returns current timestamp as ISO string — safe for Redis/JSON."""
    return datetime.datetime.utcnow().isoformat() + "Z"


# ══════════════════════════════════════════════════════════════════════════════
# AGENT SINGLETONS
# ══════════════════════════════════════════════════════════════════════════════

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



# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _safe_text(value: Any, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _safe_int(value: Any, default: int = 5) -> int:
    try:
        parsed = int(value)
        return max(1, min(10, parsed))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.5) -> float:
    try:
        parsed = float(value)
        return max(0.0, min(1.0, parsed))
    except Exception:
        return default


def _confidence_label_to_float(label: str, default: float = 0.5) -> float:
    mapping = {"LOW": 0.35, "MEDIUM": 0.6, "HIGH": 0.85}
    return mapping.get(_safe_text(label, "").upper(), default)


def _normalized_cause(cause: Dict[str, Any], fallback_id: str) -> Dict[str, Any]:
    """Normalize cause dict with safe defaults."""
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
            "cause_text": "Data mapping mismatch between source and template fields",
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



# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — INITIALIZE
# Validates input and sets up initial state
# ══════════════════════════════════════════════════════════════════════════════

def initialize_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 0] Initialize: validating input and setting up state...")
    log_node_entry("initialize", state)

    complaint = _safe_text(state.get("complaint"), "")
    complaint_id = _safe_text(state.get("complaint_id"), "")

    if not complaint_id:
        error_msg = "complaint_id is required"
        log_error("initialize", error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "stopping_reason": "invalid_input",
            "node_log": [{"node": "initialize", "status": "error", "error": error_msg, "timestamp": _now()}],
        }

    if not complaint:
        error_msg = "complaint is required"
        log_error("initialize", error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "stopping_reason": "invalid_input",
            "node_log": [{"node": "initialize", "status": "error", "error": error_msg, "timestamp": _now()}],
        }

    fmea_path = state.get("fmea_document_path")
    has_fmea = bool(fmea_path and os.path.exists(fmea_path))
    mode = "FMEA_ITERATIVE" if has_fmea else "NO_FMEA_SINGLE_SHOT"

    print(f"   Complaint ID : {complaint_id}")
    print(f"   Mode         : {mode}")
    print(f"   FMEA         : {'YES' if has_fmea else 'NO'}")

    log_node_exit("initialize", {"status": "success"})
    return {
        "has_fmea": has_fmea,
        "mode": mode,
        "current_loop_count": 0,
        "status": "running",
        "node_log": [{"node": "initialize", "status": "success", "mode": mode, "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — PAYLOAD BUILDER
# Builds all agent payloads using payloads.py
# ══════════════════════════════════════════════════════════════════════════════

def payload_builder_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 1] Payload Builder: building per-agent inputs...")
    log_node_entry("payload_builder", state)

    payloads = build_all_payloads(state)

    print(f"   Built payloads for: {list(payloads.keys())}")
    log_node_exit("payload_builder", {"status": "complete"})
    return {
        "agent_payloads": payloads,
        "node_log": [{"node": "payload_builder", "status": "complete", "timestamp": _now()}],
    }



# ══════════════════════════════════════════════════════════════════════════════
# NODE 3 — QUESTION AGENT
# Generates Why question
# ══════════════════════════════════════════════════════════════════════════════

def question_agent_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 2] Question Agent: generating Why question...")
    log_node_entry("question_agent", state)

    payloads = state.get("agent_payloads", {})
    question_payload = payloads.get("question", {})
    
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_question_agent()
            
            if question_payload.get("type") == "start":
                start_input = StartWhyInput(
                    complaint_id=question_payload["complaint_id"],
                    complaint=question_payload["complaint"],
                    evidence=question_payload["evidence"],
                    sop=question_payload["sop"],
                )
                result = agent.start(start_input)
            else:
                continue_input = ContinueWhyInput(
                    complaint_id=question_payload["complaint_id"],
                    answer=question_payload["answer"],
                )
                result = agent.continue_chain(continue_input)

            result_serialized = deep_serialize(result)
            
            if result_serialized.get("error") or not result_serialized.get("why_question"):
                error_msg = _safe_text(result_serialized.get("error"), "Question generation failed")
                log_error("question_agent", error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "stopping_reason": "question_generation_failed",
                    "node_log": [{"node": "question_agent", "status": "error", "error": error_msg, "timestamp": _now()}],
                }

            print(f"   Question : {result_serialized.get('why_question')[:80]}...")
            log_node_exit("question_agent", {"status": "success"})
            return {
                "current_loop_count": int(state.get("current_loop_count", 0)) + 1,
                "current_why_question": result_serialized.get("why_question"),
                "current_why_reasoning": result_serialized.get("reasoning") or "",
                "current_question_result": result_serialized,
                "node_log": [{"node": "question_agent", "status": "success", 
                             "loop": int(state.get("current_loop_count", 0)) + 1, "timestamp": _now()}],
            }

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("question_agent", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    error_msg = f"Question agent failure after {MAX_NODE_RETRIES} attempts: {last_exc}"
    log_error("question_agent", error_msg)
    return {
        "status": "error",
        "error": error_msg,
        "stopping_reason": "question_generation_exception",
        "node_log": [{"node": "question_agent", "status": "error", "error": error_msg, "timestamp": _now()}],
    }



# ══════════════════════════════════════════════════════════════════════════════
# NODE 4 — CAUSE GENERATION AGENT
# Generates list of potential causes
# ══════════════════════════════════════════════════════════════════════════════

def cause_generation_agent_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 3] Cause Generation Agent: generating causes...")
    log_node_entry("cause_generation_agent", state)

    # Rebuild cause_generation payload with current question
    # (Question is generated dynamically, so we can't pre-build this payload)
    from .payloads import cause_generation_payload
    cause_payload = cause_generation_payload(state)
    
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_cause_agent()
            
            question_input_dict = cause_payload.get("question_input", {})
            question_input = QuestionInput(
                question_id=question_input_dict["question_id"],
                question=question_input_dict["question"],
                context=question_input_dict.get("context"),
                evidence_context=question_input_dict.get("evidence_context"),
            )
            
            fmea_path = cause_payload.get("fmea_document_path")
            
            # Convert relative path to absolute if needed
            if fmea_path and not os.path.isabs(fmea_path):
                fmea_path = os.path.abspath(fmea_path)
                print(f"   FMEA path (absolute): {fmea_path}")
            
            # Check if FMEA file exists
            if fmea_path and not os.path.exists(fmea_path):
                print(f"   [WARNING] FMEA file not found: {fmea_path}")
                fmea_path = None
            
            result = agent.process_question(question_input=question_input, fmea_document_path=fmea_path)
            result_serialized = deep_serialize(result)

            causes_raw = result_serialized.get("causes") or []
            causes = [_normalized_cause(c, f"C-{idx + 1:03d}") for idx, c in enumerate(causes_raw)]

            # If FMEA returns no causes, retry in LLM-only mode
            if not causes and fmea_path:
                print("   [WARNING] FMEA returned 0 causes. Retrying in LLM-only mode...")
                retry_result = agent.process_question(question_input=question_input, fmea_document_path=None)
                retry_result_serialized = deep_serialize(retry_result)
                retry_causes_raw = retry_result_serialized.get("causes") or []
                if retry_causes_raw:
                    causes = [_normalized_cause(c, f"C-{idx + 1:03d}") for idx, c in enumerate(retry_causes_raw)]
                    result_serialized = retry_result_serialized

            # Fallback causes if still empty
            if not causes:
                print("   [WARNING] No causes generated. Using fallback causes...")
                causes = _build_fallback_causes(state.get("current_why_question") or "")
                result_serialized["matched_entries"] = 0
                result_serialized["notes"] = "Generated deterministic fallback causes after empty upstream output."

            print(f"   Causes generated : {len(causes)}")
            print(f"   FMEA matched     : {result_serialized.get('matched_entries', 0)}")
            
            log_node_exit("cause_generation_agent", {"status": "success", "causes_count": len(causes)})
            return {
                "current_causes": causes,
                "current_total_causes": len(causes),
                "current_fmea_matched": int(result_serialized.get("matched_entries") or 0),
                "current_cause_generation_result": result_serialized,
                "node_log": [{"node": "cause_generation_agent", "status": "success", 
                             "causes_count": len(causes), "timestamp": _now()}],
            }

        except Exception as exc:
            last_exc = exc
            print(f"   [X] Attempt {attempt + 1} failed: {exc}")
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("cause_generation_agent", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    error_msg = f"Cause generation failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    print(f"   [X] {error_msg}")
    log_error("cause_generation_agent", error_msg)
    return {
        "status": "error",
        "error": error_msg,
        "stopping_reason": "cause_generation_exception",
        "node_log": [{"node": "cause_generation_agent", "status": "error", "error": error_msg, "timestamp": _now()}],
    }



# ══════════════════════════════════════════════════════════════════════════════
# NODE 5 — VALIDATION AGENT
# Validates causes against evidence
# ══════════════════════════════════════════════════════════════════════════════

def validation_agent_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 4] Validation Agent: validating causes against evidence...")
    log_node_entry("validation_agent", state)

    # Rebuild validation payload with current causes
    # (Causes are generated dynamically, so we can't pre-build this payload)
    from .payloads import validation_payload as build_validation_payload
    validation_payload = build_validation_payload(state)
    
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_validation_agent()
            
            # Build ValidationInput from payload
            generated_causes = [GeneratedCause(**c) for c in validation_payload["generated_causes"]]
            validation_input = ValidationInput(
                complaint_id=validation_payload["complaint_id"],
                question=validation_payload["question"],
                generated_causes=generated_causes,
                complaint_description=validation_payload["complaint_description"],
                logs=validation_payload.get("logs"),
                reports=validation_payload.get("reports"),
                process_data=validation_payload.get("process_data"),
                historical_capa=validation_payload.get("historical_capa"),
                policies=validation_payload.get("policies"),
                sop=validation_payload.get("sop"),
                investigation_records=validation_payload.get("investigation_records"),
                supporting_system_information=validation_payload.get("supporting_system_information"),
                investigation_evidence=validation_payload.get("investigation_evidence", {}),
            )
            
            result = agent.validate_causes(validation_input)
            result_serialized = deep_serialize(result)
            
            valid_items = result_serialized.get("validated_causes") or []
            causes = state.get("current_causes") or []
            cause_lookup = {c["cause_id"]: c for c in causes}

            # Enrich validated causes with original data
            enriched_validated = []
            for item in valid_items:
                cid = _safe_text(item.get("cause_id"), "")
                base = _normalized_cause(cause_lookup.get(cid, {}), cid or "C-UNKNOWN")
                enriched_validated.append({
                    **base,
                    "evidence_match_status": _safe_text(item.get("evidence_match_status"), "unknown"),
                    "supporting_evidence_references": item.get("supporting_evidence_references") or [],
                    "validation_confidence": _safe_float(item.get("confidence"), 0.5),
                    "validation_rationale": _safe_text(item.get("rationale"), "No rationale provided"),
                })

            valid_count = len(enriched_validated)
            print(f"   Validated causes : {valid_count}")
            
            log_node_exit("validation_agent", {"status": "success", "validated_count": valid_count})
            return {
                "validation_result": result_serialized,
                "validated_causes_enriched": enriched_validated,
                "node_log": [{"node": "validation_agent", "status": "success", 
                             "validated_count": valid_count, "timestamp": _now()}],
            }

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("validation_agent", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    error_msg = f"Validation failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    log_error("validation_agent", error_msg)
    return {
        "status": "error",
        "error": error_msg,
        "stopping_reason": "validation_exception",
        "node_log": [{"node": "validation_agent", "status": "error", "error": error_msg, "timestamp": _now()}],
    }



# ══════════════════════════════════════════════════════════════════════════════
# NODE 6 — HUMAN REVIEW
# Pauses workflow for human cause selection
# ══════════════════════════════════════════════════════════════════════════════

def human_review_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 5] Human Review: awaiting human cause selection...")
    log_node_entry("human_review", state)

    human_selected_id = state.get("human_selected_cause_id")
    
    if not human_selected_id:
        # Still waiting for human input - build output for pause state
        all_validated_causes = state.get("validated_causes_enriched") or []
        
        # Filter to only show causes with ≥90% confidence AND matched status
        high_confidence_matched_causes = [
            cause for cause in all_validated_causes 
            if cause.get("validation_confidence", 0) >= 0.90 
            and cause.get("evidence_match_status", "").lower() == "matched"
        ]
        
        print(f"   Total validated causes: {len(all_validated_causes)}")
        print(f"   High confidence (≥90%): {sum(1 for c in all_validated_causes if c.get('validation_confidence', 0) >= 0.90)}")
        print(f"   Matched status: {sum(1 for c in all_validated_causes if c.get('evidence_match_status', '').lower() == 'matched')}")
        print(f"   High confidence + Matched: {len(high_confidence_matched_causes)}")
        
        # Check if there are NO qualified causes - should go to zero evidence mode
        if len(high_confidence_matched_causes) == 0:
            print(f"   [WARNING] No qualified causes found in iteration {state.get('current_loop_count', 0)}")
            print(f"   [INFO] Routing to zero_evidence_agent to select from all validated causes")
            log_node_exit("human_review", {"status": "no_qualified_causes", "routing": "zero_evidence_agent"})
            return {
                "status": "running",  # Continue workflow
                "awaiting_human_review": False,
                "node_log": [{"node": "human_review", "status": "no_qualified_causes", 
                             "routing": "zero_evidence_agent", "timestamp": _now()}],
            }
        
        print(f"   Awaiting selection from {len(high_confidence_matched_causes)} qualified causes")
        
        # CRITICAL: Use actual current iteration from iteration_outputs, not stale current_loop_count
        iteration_history = list(state.get("iteration_outputs", []))
        actual_current_iteration = max([io.get("iteration", 0) for io in iteration_history], default=0) if iteration_history else int(state.get("current_loop_count", 0))
        
        # If we have iteration_history but current_loop_count is higher, use current_loop_count
        # This handles the case where we just completed a new iteration
        state_loop_count = int(state.get("current_loop_count", 0))
        if state_loop_count > actual_current_iteration:
            actual_current_iteration = state_loop_count
        
        print(f"   [DEBUG] Building iteration_output for iteration {actual_current_iteration}")
        print(f"   [DEBUG] Existing iteration_outputs has {len(iteration_history)} entries: {[io.get('iteration') for io in iteration_history]}")
        
        # Build iteration_outputs for current iteration
        current_iteration_output = {
            "iteration": actual_current_iteration,
            "question": state.get("current_why_question", ""),
            "generated_causes": state.get("current_causes", []),  # ALL causes from cause generation
            "validated_causes": all_validated_causes,  # ALL validated causes
            "qualified_causes": high_confidence_matched_causes,  # Only qualified causes (≥90% + matched)
            "selected_cause_id": None,  # Will be updated when human selects
        }
        
        # Check if this iteration already exists (avoid duplicates)
        existing_idx = None
        for idx, iter_out in enumerate(iteration_history):
            if iter_out.get("iteration") == actual_current_iteration:
                existing_idx = idx
                break
        
        if existing_idx is not None:
            # Update existing iteration
            print(f"   [DEBUG] Updating existing iteration {actual_current_iteration}")
            iteration_history[existing_idx] = current_iteration_output
        else:
            # Add new iteration
            print(f"   [DEBUG] Adding new iteration {actual_current_iteration}")
            iteration_history.append(current_iteration_output)
        
        print(f"   [DEBUG] After update, iteration_outputs has {len(iteration_history)} entries: {[io.get('iteration') for io in iteration_history]}")
        
        # Build final output for paused state
        execution_time = round(time.time() - float(state.get("start_time") or time.time()), 4)
        final_output = {
            "complaint_id": state.get("complaint_id"),
            "session_id": state.get("session_id"),
            "status": "awaiting_human_review",
            "mode": state.get("mode", "NO_FMEA_SINGLE_SHOT"),
            "analysis_depth": int(state.get("current_loop_count", 0)),
            "ai_flagged": False,
            "manual_investigation_required": False,
            "stopping_reason": None,
            "awaiting_human_review": True,
            "human_review_message": f"Please review and select one of the {len(high_confidence_matched_causes)} qualified cause(s) (≥90% confidence + matched evidence).",
            "validated_causes": high_confidence_matched_causes,  # Only send qualified causes
            "root_cause": None,
            "why_chain": state.get("why_chain", []),
            "iteration_outputs": iteration_history,  # ADD THIS - complete iteration history
            "validation_summary": {
                "total_input_causes": (state.get("validation_result") or {}).get("total_input_causes", 0),
                "total_validated_causes": (state.get("validation_result") or {}).get("total_validated_causes", 0),
                "high_confidence_matched_causes": len(high_confidence_matched_causes),  # Add this info
                "overall_confidence": (state.get("validation_result") or {}).get("overall_confidence"),
            },
            "execution_time_seconds": execution_time,
            "error": None,
            "node_log": state.get("node_log", []) + [{"node": "human_review", "status": "awaiting_input", "timestamp": _now()}],
            "errors": state.get("errors", []),
        }
        
        log_node_exit("human_review", {"status": "awaiting_input"})
        return {
            "status": "awaiting_human_review",  # Set status in state
            "awaiting_human_review": True,
            "human_review_message": f"Please review and select one of the {len(high_confidence_matched_causes)} qualified cause(s) (≥90% confidence + matched evidence).",
            "iteration_outputs": iteration_history,  # Store in state for next iteration
            "final_output": deep_serialize(final_output),
            "node_log": [{"node": "human_review", "status": "awaiting_input", "timestamp": _now()}],
        }

    # Human has selected a cause
    all_validated_causes = state.get("validated_causes_enriched") or []
    
    # Filter to only qualified causes (high confidence + matched)
    qualified_causes = [
        cause for cause in all_validated_causes 
        if cause.get("validation_confidence", 0) >= 0.90 
        and cause.get("evidence_match_status", "").lower() == "matched"
    ]
    
    # CRITICAL FIX: Use the LATEST iteration number from iteration_outputs, not current_loop_count
    # because current_loop_count might be stale from Redis
    iteration_history = list(state.get("iteration_outputs", []))
    actual_current_iteration = max([io.get("iteration", 0) for io in iteration_history], default=0) if iteration_history else int(state.get("current_loop_count", 0))
    
    print(f"   [DEBUG] Current loop count from state: {state.get('current_loop_count', 0)}")
    print(f"   [DEBUG] Actual current iteration (from iteration_outputs): {actual_current_iteration}")
    print(f"   [DEBUG] Existing iteration_outputs: {len(iteration_history)} entries")
    print(f"   [DEBUG] iteration_outputs: {[io.get('iteration') for io in iteration_history]}")
    
    selected_cause = None
    
    # Validate selection is from qualified causes only
    for cause in qualified_causes:
        if cause.get("cause_id") == human_selected_id:
            selected_cause = cause
            break
    
    if not selected_cause:
        error_msg = f"Selected cause_id '{human_selected_id}' not found in qualified causes (≥90% confidence + matched evidence)"
        log_error("human_review", error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "stopping_reason": "invalid_human_selection",
            "node_log": [{"node": "human_review", "status": "error", "error": error_msg, "timestamp": _now()}],
        }

    confidence = _safe_float(selected_cause.get("validation_confidence"), 0.5)
    human_decision = state.get("human_decision", "root_cause")  # Default to root_cause
    
    # Add to why chain (check for duplicates first)
    chain_history = list(state.get("why_chain") or [])
    current_loop = int(state.get("current_loop_count", 0))
    
    # Check if this loop already has an entry
    existing_entry = None
    for entry in chain_history:
        if entry.get("loop") == current_loop:
            existing_entry = entry
            break
    
    # Only add if not already present
    if not existing_entry:
        chain_history.append({
            "loop": current_loop,
            "question": _safe_text(state.get("current_why_question"), ""),
            "selected_cause": _safe_text(selected_cause.get("cause_text"), ""),
            "selected_cause_id": _safe_text(selected_cause.get("cause_id"), ""),
            "confidence": confidence,
            "human_approved": True,
            "decision": human_decision,
        })
        print(f"   Added to why_chain: Loop {current_loop}")
    else:
        print(f"   Loop {current_loop} already in why_chain, skipping duplicate")

    print(f"   Selected : {selected_cause.get('cause_id')} (confidence: {confidence:.2f})")
    print(f"   Decision : {human_decision}")
    
    # Check if human wants to continue or end
    if human_decision == "continue":
        # Update iteration_outputs with selected cause using ACTUAL current iteration
        current_iter_num = actual_current_iteration
        
        print(f"   [DEBUG] Before update - iteration_history has {len(iteration_history)} entries")
        
        # Find and update the current iteration with selected_cause_id
        for iter_out in iteration_history:
            if iter_out.get("iteration") == current_iter_num:
                iter_out["selected_cause_id"] = human_selected_id
                print(f"   [DEBUG] Updated iteration {current_iter_num} with selected_cause_id: {human_selected_id}")
                break
        
        print(f"   [DEBUG] After update - iteration_history has {len(iteration_history)} entries")
        print(f"   [DEBUG] Iterations: {[io.get('iteration') for io in iteration_history]}")
        
        # Continue to next Why iteration
        print(f"   Action   : Continue to next Why iteration (loop {actual_current_iteration + 1})")
        log_node_exit("human_review", {"status": "continue", "selected_id": human_selected_id})
        return {
            "current_selected_cause": selected_cause,
            "current_cause_confidence": confidence,
            "why_chain": chain_history,
            "iteration_outputs": iteration_history,  # CRITICAL: Preserve iteration history for next iteration
            "awaiting_human_review": False,
            "human_review_message": None,
            "human_decision": None,  # Reset for next iteration
            "human_selected_cause_id": None,  # Reset for next iteration
            "status": "running",
            "node_log": [{"node": "human_review", "status": "continue", 
                         "selected_id": human_selected_id, "next_loop": actual_current_iteration + 1, 
                         "timestamp": _now()}],
        }
    else:
        # Treat as root cause and end analysis
        print(f"   Action   : End analysis - root cause identified")
        log_node_exit("human_review", {"status": "success", "selected_id": human_selected_id})
        return {
            "current_selected_cause": selected_cause,
            "current_cause_confidence": confidence,
            "why_chain": chain_history,
            "awaiting_human_review": False,
            "human_review_message": None,
            "final_root_cause": {
                **selected_cause,
                "reason": f"Human-approved root cause with {confidence:.0%} validation confidence",
                "confidence_score": confidence,
                "selection_path": "human_review",
            },
            "status": "completed",
            "stopping_reason": "human_approved_root_cause",
            "node_log": [{"node": "human_review", "status": "success", 
                         "selected_id": human_selected_id, "timestamp": _now()}],
        }



# ══════════════════════════════════════════════════════════════════════════════
# NODE 7 — ZERO EVIDENCE MODE
# Selects cause by criticality when no validated causes
# ══════════════════════════════════════════════════════════════════════════════

def zero_evidence_agent_node(state: WhyAnalysisV3State) -> dict:
    print("\n[STEP 5-ALT] Zero Evidence Agent: selecting by criticality...")
    log_node_entry("zero_evidence_agent", state)

    print(f"   [DEBUG] Current loop count: {state.get('current_loop_count', 0)}")
    print(f"   [DEBUG] Existing iteration_outputs: {len(state.get('iteration_outputs', []))} entries")
    print(f"   [DEBUG] iteration_outputs: {[io.get('iteration') for io in state.get('iteration_outputs', [])]}")

    # Rebuild zero_evidence payload with current causes
    # (Causes are generated dynamically, so we can't pre-build this payload)
    from .payloads import zero_evidence_payload as build_zero_evidence_payload
    ze_payload = build_zero_evidence_payload(state)
    
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_NODE_RETRIES):
        try:
            agent = _get_zero_evidence_agent()
            
            # Build ZeroEvidenceInput from payload
            ze_causes = [ZeroEvidenceCauseInput(**c) for c in ze_payload["causes"]]
            ze_input = ZeroEvidenceInput(
                question_id=ze_payload["question_id"],
                question=ze_payload["question"],
                causes=ze_causes,
                total_causes=ze_payload["total_causes"],
            )
            
            result = agent.analyze(ze_input)
            result_serialized = deep_serialize(result)
            
            selected = result_serialized.get("selected_root_cause") or {}
            selected_cause_id = _safe_text(selected.get("cause_id"), "")
            
            # Find original cause
            causes = state.get("current_causes") or []
            selected_source = None
            for cause in causes:
                if cause.get("cause_id") == selected_cause_id:
                    selected_source = cause
                    break
            
            if not selected_source:
                selected_source = causes[0] if causes else {}

            reason = _safe_text(selected.get("reason"), 
                               "No validated causes found. Zero evidence mode selected highest criticality cause.")
            confidence = _confidence_label_to_float(result_serialized.get("confidence"), 0.6)

            final_root = {
                **_normalized_cause(selected_source, "ROOT-UNKNOWN"),
                "reason": reason,
                "confidence_score": confidence,
                "selection_path": "zero_evidence_mode",
            }

            print(f"   Selected : {selected_cause_id} (confidence: {confidence:.2f})")
            
            # Build iteration_outputs for current iteration (Zero Evidence path)
            all_validated_causes = state.get("validated_causes_enriched") or []
            current_iteration_output = {
                "iteration": int(state.get("current_loop_count", 0)),
                "question": state.get("current_why_question", ""),
                "generated_causes": state.get("current_causes", []),  # ALL causes from cause generation
                "validated_causes": all_validated_causes,  # ALL validated causes
                "qualified_causes": [],  # No qualified causes (that's why Zero Evidence ran)
                "zero_evidence_selected": final_root,  # The cause selected by Zero Evidence
                "selected_cause_id": selected_cause_id,  # The cause ID selected by Zero Evidence
            }
            
            # Append to iteration_outputs history
            iteration_history = list(state.get("iteration_outputs", []))
            
            # Check if this iteration already exists (avoid duplicates)
            current_iter_num = int(state.get("current_loop_count", 0))
            existing_idx = None
            for idx, iter_out in enumerate(iteration_history):
                if iter_out.get("iteration") == current_iter_num:
                    existing_idx = idx
                    break
            
            if existing_idx is not None:
                # Update existing iteration
                iteration_history[existing_idx] = current_iteration_output
            else:
                # Add new iteration
                iteration_history.append(current_iteration_output)
            
            log_node_exit("zero_evidence_agent", {"status": "success", "selected_id": selected_cause_id})
            return {
                "zero_evidence_result": result_serialized,
                "current_selected_cause": selected_source,
                "current_cause_confidence": confidence,
                "final_root_cause": final_root,
                "iteration_outputs": iteration_history,  # ADD THIS - store iteration history
                "status": "ai_flagged",
                "ai_flagged": True,
                "stopping_reason": "no_validated_cause_zero_evidence",
                "node_log": [{"node": "zero_evidence_agent", "status": "success", 
                             "selected_id": selected_cause_id, "timestamp": _now()}],
            }

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_NODE_RETRIES - 1:
                log_error("zero_evidence_agent", f"Attempt {attempt + 1} failed: {exc}. Retrying...")

    error_msg = f"Zero evidence mode failed after {MAX_NODE_RETRIES} attempts: {last_exc}"
    log_error("zero_evidence_agent", error_msg)
    return {
        "status": "error",
        "error": error_msg,
        "stopping_reason": "zero_evidence_exception",
        "node_log": [{"node": "zero_evidence_agent", "status": "error", "error": error_msg, "timestamp": _now()}],
    }



# ══════════════════════════════════════════════════════════════════════════════
# NODE 8 — FINALIZE
# Assembles final output
# ══════════════════════════════════════════════════════════════════════════════

def finalize_node(state: WhyAnalysisV3State) -> dict:
    print("\n[COMPLETE] Why Analysis V3 complete - building final report...")
    log_node_entry("finalize", state)

    execution_time = round(time.time() - float(state.get("start_time") or time.time()), 4)
    status = _safe_text(state.get("status"), "error")

    final_output = {
        "complaint_id": state.get("complaint_id"),
        "session_id": state.get("session_id"),
        "status": status,
        "mode": state.get("mode", "NO_FMEA_SINGLE_SHOT"),
        "analysis_depth": int(state.get("current_loop_count", 0)),
        "ai_flagged": bool(state.get("ai_flagged", False)),
        "manual_investigation_required": bool(state.get("manual_investigation_required", False)),
        "stopping_reason": state.get("stopping_reason"),
        "awaiting_human_review": bool(state.get("awaiting_human_review", False)),
        "human_review_message": state.get("human_review_message"),
        "validated_causes": state.get("validated_causes_enriched", []) if state.get("awaiting_human_review") else None,
        "root_cause": state.get("final_root_cause"),
        "why_chain": state.get("why_chain", []),
        "iteration_outputs": state.get("iteration_outputs", []),  # ADD THIS - include all iteration outputs
        "validation_summary": {
            "total_input_causes": (state.get("validation_result") or {}).get("total_input_causes", 0),
            "total_validated_causes": (state.get("validation_result") or {}).get("total_validated_causes", 0),
            "overall_confidence": (state.get("validation_result") or {}).get("overall_confidence"),
        },
        "execution_time_seconds": execution_time,
        "error": state.get("error"),
        "node_log": state.get("node_log", []),
        "errors": state.get("errors", []),
    }

    print(f"   Final status : {final_output['status']}")
    print(f"   Execution time : {execution_time:.2f}s")
    
    log_node_exit("finalize", {"status": "complete"})
    return {
        "final_output": deep_serialize(final_output),
        "node_log": [{"node": "finalize", "status": "complete", "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# All routing logic lives here — not inside node functions
# ══════════════════════════════════════════════════════════════════════════════

def route_after_initialize(state: WhyAnalysisV3State) -> str:
    if state.get("status") == "error":
        return "finalize"
    return "payload_builder"


def route_after_payload_builder(state: WhyAnalysisV3State) -> str:
    return "question_agent"


def route_after_question(state: WhyAnalysisV3State) -> str:
    if state.get("status") == "error":
        return "finalize"
    return "cause_generation_agent"


def route_after_causes(state: WhyAnalysisV3State) -> str:
    if state.get("status") == "error":
        return "finalize"
    return "validation_agent"


def route_after_validation(state: WhyAnalysisV3State) -> str:
    if state.get("status") == "error":
        return "finalize"
    
    validated_causes = state.get("validated_causes_enriched") or []
    validated_count = len(validated_causes)
    
    if validated_count == 0:
        return "zero_evidence_agent"
    
    # Check if any cause has BOTH confidence >= 0.90 AND matched status
    qualified_causes = [
        cause for cause in validated_causes
        if cause.get("validation_confidence", 0) >= 0.90 
        and cause.get("evidence_match_status", "").lower() == "matched"
    ]
    
    if len(qualified_causes) > 0:
        # At least one cause with 90%+ confidence AND matched -> human review
        print(f"   [INFO] Found {len(qualified_causes)} qualified causes (≥90% + matched) -> Human Review")
        return "human_review"
    else:
        # No causes meet both criteria -> zero evidence mode
        print(f"   [INFO] No causes meet criteria (≥90% + matched) -> Zero Evidence Mode")
        print(f"   [INFO] Total validated: {validated_count}, High confidence: {sum(1 for c in validated_causes if c.get('validation_confidence', 0) >= 0.90)}, Matched: {sum(1 for c in validated_causes if c.get('evidence_match_status', '').lower() == 'matched')}")
        return "zero_evidence_agent"


def route_after_human_review(state: WhyAnalysisV3State) -> str:
    if state.get("status") == "error":
        return "finalize"
    if state.get("awaiting_human_review"):
        return END  # Pause workflow
    if state.get("status") == "running":
        # Human chose to continue - go back to payload_builder for next iteration
        print(f"   [ROUTING] Human chose continue -> going to payload_builder for next iteration")
        return "payload_builder"
    # Human chose root_cause or workflow completed
    return "finalize"


def route_after_zero_evidence(state: WhyAnalysisV3State) -> str:
    return "finalize"


def route_after_finalize(state: WhyAnalysisV3State) -> str:
    return END



# ══════════════════════════════════════════════════════════════════════════════
# BUILD GRAPH
# All routing lives here — full flow visible in one place
# ══════════════════════════════════════════════════════════════════════════════

def build_orchestrator():
    """
    Assembles the full Why Analysis V3 Orchestrator graph.

    Topology:
        START
          └─► initialize
                └─► payload_builder
                      └─► question_agent
                            └─► cause_generation_agent
                                  └─► validation_agent
                                        ├─► (0 causes) → zero_evidence_agent → finalize → END
                                        └─► (1+ causes) → human_review
                                                            ├─► (awaiting) → END (paused)
                                                            └─► (selected) → finalize → END
    """
    g = StateGraph(WhyAnalysisV3State)

    # ── Register nodes ────────────────────────────────────────────────────────
    g.add_node("initialize", initialize_node)
    g.add_node("payload_builder", payload_builder_node)
    g.add_node("question_agent", question_agent_node)
    g.add_node("cause_generation_agent", cause_generation_agent_node)
    g.add_node("validation_agent", validation_agent_node)
    g.add_node("human_review", human_review_node)
    g.add_node("zero_evidence_agent", zero_evidence_agent_node)
    g.add_node("finalize", finalize_node)

    # ── Entry ─────────────────────────────────────────────────────────────────
    g.add_edge(START, "initialize")

    # ── Routing ───────────────────────────────────────────────────────────────
    g.add_conditional_edges(
        "initialize",
        route_after_initialize,
        {
            "payload_builder": "payload_builder",
            "finalize": "finalize",
        }
    )

    g.add_conditional_edges(
        "payload_builder",
        route_after_payload_builder,
        {
            "question_agent": "question_agent",
        }
    )

    g.add_conditional_edges(
        "question_agent",
        route_after_question,
        {
            "cause_generation_agent": "cause_generation_agent",
            "finalize": "finalize",
        }
    )

    g.add_conditional_edges(
        "cause_generation_agent",
        route_after_causes,
        {
            "validation_agent": "validation_agent",
            "finalize": "finalize",
        }
    )

    g.add_conditional_edges(
        "validation_agent",
        route_after_validation,
        {
            "human_review": "human_review",
            "zero_evidence_agent": "zero_evidence_agent",
            "finalize": "finalize",
        }
    )

    g.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "payload_builder": "payload_builder",  # Continue to next iteration
            "zero_evidence_agent": "zero_evidence_agent",  # No qualified causes
            "finalize": "finalize",
            END: END,
        }
    )

    g.add_conditional_edges(
        "zero_evidence_agent",
        route_after_zero_evidence,
        {
            "finalize": "finalize",
        }
    )

    g.add_conditional_edges(
        "finalize",
        route_after_finalize,
        {
            END: END,
        }
    )

    # ── Compile with Redis checkpointing ──────────────────────────────────────
    # Using sync RedisSaver (same pattern as risk_analysis_orchestrator)
    from langgraph.checkpoint.redis import RedisSaver
    checkpointer = RedisSaver("redis://localhost:6379")
    checkpointer.setup()
    return g.compile(checkpointer=checkpointer)


# ── Module-level graph instance ───────────────────────────────────────────────
orchestrator_graph = build_orchestrator()
