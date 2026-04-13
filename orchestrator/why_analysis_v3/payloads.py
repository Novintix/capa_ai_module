"""
why_analysis_v3/payloads.py

Per-agent payload builders for Why Analysis V3 Orchestrator.

HOW TO USE:
  - Each function accepts (state: dict) and returns a dict
    matching the exact schema expected by the sub-agent.
  - To add a new agent → add a new function here and call it in build_all_payloads().
  - To change a payload schema → edit only the relevant function here.

Functions:
    question_payload(state)         → Question Agent
    cause_generation_payload(state) → Cause Generation Agent
    validation_payload(state)       → Validation Agent
    zero_evidence_payload(state)    → Zero Evidence Agent
    build_all_payloads(state)       → full payloads dict
"""

from typing import Any, Dict


def question_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build payload for Question Agent.
    Matches: Agents/question/schemas.py → StartWhyInput or ContinueWhyInput
    """
    loop_count = int(state.get("current_loop_count", 0))
    
    if loop_count == 0:
        # First iteration - StartWhyInput
        return {
            "type": "start",
            "complaint_id": state.get("complaint_id"),
            "complaint": state.get("complaint"),
            "evidence": state.get("evidence") or "",
            "sop": state.get("sop") or "",
        }
    else:
        # Subsequent iterations - ContinueWhyInput
        selected = state.get("current_selected_cause") or {}
        return {
            "type": "continue",
            "complaint_id": state.get("complaint_id"),
            "answer": selected.get("cause_text", "Unknown cause"),
        }


def cause_generation_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build payload for Cause Generation Agent.
    Matches: Agents/cause_generation/schemas.py → QuestionInput
    """
    loop_count = int(state.get("current_loop_count", 0))
    
    # Context: first loop uses complaint, subsequent loops use selected cause
    context_value = state.get("complaint") or ""
    if loop_count > 1:
        selected = state.get("current_selected_cause") or {}
        context_value = selected.get("cause_text", context_value)
    
    # Build evidence context with all available fields
    evidence_ctx = {"evidence": state.get("evidence") or ""}
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
        val = state.get(field)
        if val:
            evidence_ctx[field] = val
    
    return {
        "question_input": {
            "question_id": f"{state.get('complaint_id')}",
            "question": state.get("current_why_question"),
            "context": context_value,
            "evidence_context": evidence_ctx,
        },
        "fmea_document_path": state.get("fmea_document_path") if state.get("has_fmea") else None,
    }


def validation_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build payload for Validation Agent.
    Matches: Agents/validation/schemas.py → ValidationInput
    """
    causes = state.get("current_causes") or []
    
    # Convert causes to GeneratedCause format
    generated_causes = []
    for i, cause in enumerate(causes):
        generated_causes.append({
            "cause_id": cause.get("cause_id", f"C-{i + 1:03d}"),
            "cause_text": cause.get("cause_text", "Unspecified cause description"),
            "process_step": cause.get("process_step"),
            "failure_mode": cause.get("failure_mode"),
            "potential_effects": cause.get("potential_effects"),
            "severity": int(cause.get("severity")) if cause.get("severity") is not None else None,
            "occurrence": int(cause.get("occurrence")) if cause.get("occurrence") is not None else None,
            "detection": int(cause.get("detection")) if cause.get("detection") is not None else None,
            "current_controls": cause.get("current_controls"),
            "source": cause.get("source", "Generated"),
        })
    
    return {
        "complaint_id": state.get("complaint_id"),
        "question": state.get("current_why_question"),
        "generated_causes": generated_causes,
        "complaint_description": state.get("complaint") or "",
        "logs": state.get("logs"),
        "reports": state.get("reports"),
        "process_data": state.get("process_data"),
        "historical_capa": state.get("historical_capa"),
        "policies": state.get("policies"),
        "sop": state.get("sop"),
        "investigation_records": state.get("investigation_records"),
        "supporting_system_information": state.get("supporting_system_information"),
        "investigation_evidence": {
            "evidence_text": state.get("evidence") or "",
            "evidence_files": state.get("evidence_files") or [],
        },
    }


def zero_evidence_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build payload for Zero Evidence Agent.
    Matches: Agents/zero_evidence_agent/schemas.py → ZeroEvidenceInput
    """
    causes = state.get("current_causes") or []
    
    # Convert causes to ZeroEvidenceCauseInput format
    ze_causes = []
    for idx, c in enumerate(causes):
        ze_causes.append({
            "cause_id": c.get("cause_id", f"ZE-{idx + 1:03d}"),
            "cause_text": c.get("cause_text", "Unspecified cause description"),
            "process_step": c.get("process_step", "Unknown process step"),
            "failure_mode": c.get("failure_mode", "Unspecified failure mode"),
            "potential_effects": c.get("potential_effects"),
            "severity": int(c.get("severity", 5)),
            "occurrence": int(c.get("occurrence", 5)),
            "detection": int(c.get("detection", 5)),
            "current_controls": c.get("current_controls", "Not provided"),
            "source": c.get("source", "unknown"),
        })
    
    return {
        "question_id": f"{state.get('complaint_id')}",
        "question": state.get("current_why_question") or "",
        "causes": ze_causes,
        "total_causes": len(ze_causes),
    }


def build_all_payloads(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assembles all agent payloads into one dict.
    
    Args:
        state: Full orchestrator state
        
    Returns:
        Dict with keys: question, cause_generation, validation, zero_evidence
    """
    return {
        "question": question_payload(state),
        "cause_generation": cause_generation_payload(state),
        "validation": validation_payload(state),
        "zero_evidence": zero_evidence_payload(state),
    }
