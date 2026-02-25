import json
import os
import httpx
import asyncio
from dotenv import load_dotenv
from typing import Any, Dict, Optional
from orchestrator_service.state import RiskAssessmentState
from orchestrator_service.logger import log_node_entry, log_node_exit, log_error
from langchain_core.runnables import RunnableConfig

load_dotenv()

# ── Severity Agent ────────────────────────────────────────────────────────────
# Runs as a separate FastAPI service. Expects: {"issue": str}
# Returns: severity_score, severity_label, clinical_score, etc.
SEVERITY_SERVICE_URL = os.getenv("SEVERITY_SERVICE_URL", "http://localhost:8000/severity")

def call_severity_agent(issue: str) -> Dict[str, Any]:
    """HTTP POST to the Severity microservice."""
    try:
        response = httpx.post(SEVERITY_SERVICE_URL, json={"issue": issue}, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error("call_severity_agent", e)
        raise

# ── Occurrence Agent ──────────────────────────────────────────────────────────
# Runs as a separate FastAPI service. Expects Form-Data.
OCCURRENCE_SERVICE_URL = os.getenv("OCCURRENCE_SERVICE_URL", "http://localhost:8000/occurrence/analyze")

def call_occurrence_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP POST to the Occurrence microservice using Form-Data."""
    try:
        # Prepare Form-Data
        files = {
            "complaint_id": (None, str(payload.get("complaint_id", ""))),
            "description": (None, str(payload.get("description", ""))),
            "date": (None, str(payload.get("date", ""))),
            "additional_context": (None, str(payload.get("additional_context", ""))),
            "product": (None, str(payload.get("product", ""))),
            "similar_cases_json": (None, json.dumps(payload.get("similar_cases", []))),
            "source": (None, str(payload.get("source", ""))),
        }
        
        response = httpx.post(OCCURRENCE_SERVICE_URL, data=files, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error("call_occurrence_agent", e)
        raise

# ── Detection Agent ───────────────────────────────────────────────────────────
# Runs as a separate FastAPI service. Expects: {"complaint_id": str, "source": str, "description": str}
DETECTION_SERVICE_URL = os.getenv("DETECTION_SERVICE_URL", "http://localhost:8000/detection/")
DETECTION_POLICY_PATH = os.getenv("DETECTION_POLICY_PATH")

def call_detection_agent(payload: Dict[str, Any], policy_path: Optional[str] = None) -> Dict[str, Any]:
    """HTTP POST to the Detection microservice."""
    try:
        params = {}
        if policy_path:
            params["policy_path"] = policy_path
        
        # Build JSON body
        body = {
            "complaint_id": payload.get("complaint_id"),
            "source": payload.get("source"),
            "description": payload.get("description")
        }
        
        response = httpx.post(DETECTION_SERVICE_URL, json=body, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error("call_detection_agent", e)
        raise

# ── Policy Constants ──────────────────────────────────────────────────────────
POLICY_CRITICAL_SEVERITY = 9
POLICY_RPN_THRESHOLD = 300
POLICY_CONFIDENCE_THRESHOLD = 0.7
SCORE_MIN = 1
SCORE_MAX = 10


def _validate_agent_output(output: Dict[str, Any]) -> str:
    """Returns None if valid, else an error message string."""
    if not isinstance(output, dict):
        return "Output is not a dictionary"
    score = output.get("score")
    if score is None:
        return "Missing numeric score"
    if not isinstance(score, (int, float)) or not (SCORE_MIN <= score <= SCORE_MAX):
        return f"Score {score} out of policy range ({SCORE_MIN}-{SCORE_MAX})"
    confidence = output.get("confidence")
    if confidence is None:
        return "Missing confidence score"
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        return "Invalid confidence value"
    if not output.get("reasoning"):
        return "Missing explanation/reasoning"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# NODE: Input Validation
# ─────────────────────────────────────────────────────────────────────────────

def input_validation_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("input_validation_node", state, thread_id=thread_id)

    errors = []
    if not state.get("complaint_description"):
        errors.append("Missing complaint_description")
    if not state.get("complaint_id"):
        errors.append("Missing complaint_id")
    if not state.get("source"):
        errors.append("Missing source")
    if not state.get("product"):
        errors.append("Missing product")

    update = {}
    if errors:
        update["workflow_status"] = "halted"
        update["errors"] = state.get("errors", []) + errors
        update["scores_valid"] = False
    else:
        if "retry_counts" not in state:
            update["retry_counts"] = {"severity": 0, "occurrence": 0, "detection": 0}

    log_node_exit("input_validation_node", update, thread_id=thread_id)
    return update


# ─────────────────────────────────────────────────────────────────────────────
# NODE: Severity Agent
# Maps state → {"issue": complaint_description} → POST to severity service
# ─────────────────────────────────────────────────────────────────────────────
def severity_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("severity_node", state, thread_id=thread_id)

    if state.get("workflow_status") == "halted":
        return {}

    # ── Build severity-specific payload ──────────────────────────────────────
    try:
        response = call_severity_agent(issue=state["complaint_description"])
    except Exception as e:
        log_error("severity_node", e, thread_id=thread_id)
        return {"errors": [str(e)], "workflow_status": "halted"}

    # ── Map fields to standardized format ──
    mapped_response = {
        "score": response.get("severity_score"),
        "confidence": 1.0,
        "reasoning": response.get("severity_label")
    }

    validation_error = _validate_agent_output(mapped_response)

    update = {
        "severity_invoked": True,
        "agent_outputs": {"severity": response},
    }

    if validation_error:
        current_retries = state.get("retry_counts", {}).get("severity", 0)
        if current_retries < 1:
            update["retry_counts"] = {"severity": current_retries + 1}
        else:
            update["escalation_required"] = True
            update["escalation_reason"] = f"Severity Agent Validation Failed: {validation_error}"
            update["workflow_status"] = "escalated"
    else:
        update["severity_score"] = mapped_response["score"]

        if mapped_response["score"] >= POLICY_CRITICAL_SEVERITY:
            update["escalation_required"] = True
            update["escalation_reason"] = (
                f"Severity Score {mapped_response['score']} >= Critical Threshold {POLICY_CRITICAL_SEVERITY}"
            )
            update["workflow_status"] = "escalated"

        if mapped_response["confidence"] < POLICY_CONFIDENCE_THRESHOLD:
            update["escalation_required"] = True
            update["escalation_reason"] = (
                f"Severity Confidence {mapped_response['confidence']} < Threshold {POLICY_CONFIDENCE_THRESHOLD}"
            )
            update["workflow_status"] = "escalated"

    log_node_exit("severity_node", update, thread_id=thread_id)
    return update


# ─────────────────────────────────────────────────────────────────────────────
# NODE: Occurrence Agent
# Maps state → occurrence agent payload format
# ─────────────────────────────────────────────────────────────────────────────
def occurrence_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("occurrence_node", state, thread_id=thread_id)

    if state.get("workflow_status") in ["halted", "escalated"]:
        return {}

    # ── Build occurrence-specific payload ─────────────────────────────────────
    payload = {
        "complaint_id": state.get("complaint_id"),
        "description": state.get("complaint_description"),
        "source": state.get("source"),
        "date": state.get("date"),
        "product": state.get("product"),
        "additional_context": state.get("additional_context", ""),
        "similar_cases": state.get("similar_cases", []),
    }
    try:
        response = call_occurrence_agent(payload)
    except Exception as e:
        log_error("occurrence_node", e, thread_id=thread_id)
        return {"errors": [str(e)], "workflow_status": "halted"}

    # ── Map fields to standardized format ──
    breakdown = response.get("breakdown", {})
    mapped_response = {
        "score": response.get("weighted_score"),
        "confidence": 0.85,
        "reasoning": breakdown.get("reasoning", response.get("rating"))
    }

    validation_error = _validate_agent_output(mapped_response)

    update = {
        "occurrence_invoked": True,
        "agent_outputs": {"occurrence": response},
    }

    if validation_error:
        current_retries = state.get("retry_counts", {}).get("occurrence", 0)
        if current_retries < 1:
            update["retry_counts"] = {"occurrence": current_retries + 1}
        else:
            update["escalation_required"] = True
            update["escalation_reason"] = f"Occurrence Agent Validation Failed: {validation_error}"
            update["workflow_status"] = "escalated"
    else:
        update["occurrence_score"] = mapped_response["score"]
        if mapped_response["confidence"] < POLICY_CONFIDENCE_THRESHOLD:
            update["escalation_required"] = True
            update["escalation_reason"] = (
                f"Occurrence Confidence {mapped_response['confidence']} < Threshold {POLICY_CONFIDENCE_THRESHOLD}"
            )
            update["workflow_status"] = "escalated"

    log_node_exit("occurrence_node", update, thread_id=thread_id)
    return update


# ─────────────────────────────────────────────────────────────────────────────
# NODE: Detection Agent
# Maps state → detection agent payload format
# ─────────────────────────────────────────────────────────────────────────────
def detection_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("detection_node", state, thread_id=thread_id)

    if state.get("workflow_status") in ["halted", "escalated"]:
        return {}

    # ── Build detection-specific payload ──────────────────────────────────────
    payload = {
        "complaint_id": state.get("complaint_id"),
        "source": state.get("source"),
        "description": state.get("complaint_description"),
    }
    try:
        response = call_detection_agent(payload, policy_path=state.get("policy_path"))
    except Exception as e:
        log_error("detection_node", e, thread_id=thread_id)
        return {"errors": [str(e)], "workflow_status": "halted"}

    # ── Map fields to standardized format ──
    mapped_response = {
        "score": response.get("detection_score"),
        "confidence": response.get("confidence"),
        "reasoning": response.get("explanation")
    }

    validation_error = _validate_agent_output(mapped_response)

    update = {
        "detection_invoked": True,
        "agent_outputs": {"detection": response},
    }

    if validation_error:
        current_retries = state.get("retry_counts", {}).get("detection", 0)
        if current_retries < 1:
            update["retry_counts"] = {"detection": current_retries + 1}
        else:
            update["escalation_required"] = True
            update["escalation_reason"] = f"Detection Agent Validation Failed: {validation_error}"
            update["workflow_status"] = "escalated"
    else:
        update["detection_score"] = mapped_response["score"]
        if mapped_response["confidence"] < POLICY_CONFIDENCE_THRESHOLD:
            update["escalation_required"] = True
            update["escalation_reason"] = (
                f"Detection Confidence {mapped_response['confidence']} < Threshold {POLICY_CONFIDENCE_THRESHOLD}"
            )
            update["workflow_status"] = "escalated"

    log_node_exit("detection_node", update, thread_id=thread_id)
    return update


# ─────────────────────────────────────────────────────────────────────────────
# NODE: Aggregation (RPN = Severity × Occurrence × Detection)
# ─────────────────────────────────────────────────────────────────────────────
def aggregation_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("aggregation_node", state, thread_id=thread_id)

    if state.get("workflow_status") in ["halted", "escalated"]:
        return {}

    sev = state.get("severity_score")
    occ = state.get("occurrence_score")
    det = state.get("detection_score")

    update = {}

    if None in [sev, occ, det]:
        update["escalation_required"] = True
        update["escalation_reason"] = "Missing one or more scores during aggregation"
        update["workflow_status"] = "escalated"
        update["scores_valid"] = False
    else:
        rpn = sev * occ * det
        update["rpn_computed"] = True
        update["rpn_value"] = rpn
        update["scores_valid"] = True

        if rpn >= POLICY_RPN_THRESHOLD:
            update["escalation_required"] = True
            update["escalation_reason"] = f"RPN {rpn} >= Threshold {POLICY_RPN_THRESHOLD}"
            update["workflow_status"] = "escalated"
        else:
            update["workflow_status"] = "completed"

    log_node_exit("aggregation_node", update, thread_id=thread_id)
    return update


# ─────────────────────────────────────────────────────────────────────────────
# NODE: Conflict Detection
# Checks if agent outputs are logically inconsistent with description
# ─────────────────────────────────────────────────────────────────────────────
def conflict_detection_node(state: RiskAssessmentState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"].get("thread_id")
    log_node_entry("conflict_detection_node", state, thread_id=thread_id)

    if state.get("workflow_status") in ["halted", "escalated"]:
        return {}

    sev_score = state.get("severity_score")
    description = state.get("complaint_description", "").lower()

    conflict = False
    reason = ""

    # Rule: low severity but fatal keywords in description
    if sev_score and sev_score < 5:
        if "death" in description or "fatality" in description:
            conflict = True
            reason = f"Severity {sev_score} inconsistent with keyword 'death/fatality' in description"

    update = {"conflict_detected": conflict}
    if conflict:
        update.update({
            "escalation_required": True,
            "escalation_reason": reason,
            "workflow_status": "escalated",
        })

    log_node_exit("conflict_detection_node", update, thread_id=thread_id)
    return update
