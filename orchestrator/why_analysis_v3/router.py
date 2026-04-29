"""
FastAPI router for Why Analysis V3 orchestrator.
"""

from fastapi import APIRouter, HTTPException

from .agent import WhyAnalysisV3Orchestrator
from .logger import log_api_request, log_api_response, log_error
from .orchestrator import _read_state_from_redis, orchestrator_graph
from .schemas import WhyAnalysisV3Input, WhyAnalysisV3Output, HumanReviewInput
from agent_ops import agentops_session


router = APIRouter(prefix="/why-analysis-v3", tags=["why-analysis-v3-orchestrator"])

_orchestrator: WhyAnalysisV3Orchestrator | None = None


def _get_orchestrator() -> WhyAnalysisV3Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WhyAnalysisV3Orchestrator()
    return _orchestrator


@router.post("/", response_model=WhyAnalysisV3Output)
@agentops_session(name="Why_Analysis", tags=["capa_ai_module", "why_analysis", "orchestrator"])
def run_why_analysis_v3(input_data: WhyAnalysisV3Input):
    """
    Run Why Analysis V3 using JSON input.
    
    Flow:
    1. Generate question
    2. Generate causes
    3. Validate causes
    4. If 0 validated causes -> zero_evidence_mode (terminal)
    5. If 1+ validated causes -> human_review (paused, awaiting selection)
    """
    try:
        log_api_request("/why-analysis-v3", input_data.complaint_id)

        result = _get_orchestrator().analyze(input_data)

        log_api_response(
            complaint_id=input_data.complaint_id,
            status=result.get("status", "error"),
            stopping_reason=result.get("stopping_reason"),
        )

        return WhyAnalysisV3Output(**result)

    except HTTPException:
        raise
    except Exception as exc:
        log_error("router /why-analysis-v3", str(exc))
        raise HTTPException(status_code=500, detail=f"Error running Why Analysis V3: {exc}")


@router.post("/human-review", response_model=WhyAnalysisV3Output)
@agentops_session(name="Why_Analysis_Human_Review", tags=["capa_ai_module", "why_analysis", "hitl"])
def submit_human_review(review_input: HumanReviewInput):
    """
    Submit human's cause selection to resume a paused workflow.
    
    Args:
        review_input: Contains session_id, selected_cause_id, and decision
        
    Decision options:
        - "root_cause": Treat selected cause as final root cause (end analysis)
        - "continue": Dig deeper - ask Why again with this cause (5-Why iteration)
        
    Returns:
        - If decision="root_cause": Final output with root cause
        - If decision="continue": Next iteration awaiting human review again
    """
    try:
        log_api_request("/why-analysis-v3/human-review", review_input.session_id)

        result = _get_orchestrator().resume_with_human_selection(
            session_id=review_input.session_id,
            selected_cause_id=review_input.selected_cause_id,
            decision=review_input.decision,
        )

        log_api_response(
            complaint_id=result.get("complaint_id", "unknown"),
            status=result.get("status", "error"),
            stopping_reason=result.get("stopping_reason"),
        )

        return WhyAnalysisV3Output(**result)

    except HTTPException:
        raise
    except Exception as exc:
        log_error("router /why-analysis-v3/human-review", str(exc))
        raise HTTPException(status_code=500, detail=f"Error submitting human review: {exc}")


@router.get("/status/{session_id}")
def why_analysis_v3_status(session_id: str):
    """Return summary status for a session stored in Redis."""
    result = _read_state_from_redis(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found in Redis")
    state = result.get("state", {})
    return {
        "session_id": session_id,
        "status": state.get("status") or ("completed" if state.get("final_output") else "in_progress"),
        "analysis_depth": state.get("current_loop_count", 0),
        "ai_flagged": state.get("ai_flagged", False),
        "awaiting_human_review": state.get("awaiting_human_review", False),
        "stopping_reason": state.get("stopping_reason"),
        "node_log": state.get("node_log", []),
        "errors": state.get("errors", []),
    }


@router.get("/state/{session_id}")
def why_analysis_v3_state(session_id: str):
    """Return full checkpoint state for a session stored in Redis."""
    result = _read_state_from_redis(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found in Redis")
    state = result.get("state", {})
    return {
        "session_id": session_id,
        "status": state.get("status"),
        "final_output": state.get("final_output"),
        "awaiting_human_review": state.get("awaiting_human_review", False),
        "validated_causes": state.get("validated_causes_enriched", []) if state.get("awaiting_human_review") else None,
        "node_log": state.get("node_log", []),
        "errors": state.get("errors", []),
        "current_loop_count": state.get("current_loop_count", 0),
        "stopping_reason": state.get("stopping_reason"),
    }


@router.get("/health")
def why_analysis_v3_health():
    """Health endpoint for Why Analysis V3."""
    return {
        "status": "healthy",
        "agent": "why_analysis_v3_orchestrator",
        "description": "Question -> Cause Generation -> Validation -> Human Review (or Zero Evidence if 0 causes)",
        "flow": [
            "question",
            "cause_generation",
            "validation",
            "human_review (if 1+ validated causes)",
            "zero_evidence_mode (if 0 validated causes)",
        ],
        "human_in_the_loop": True,
        "removed_agents": ["loop_control", "ranking"],
    }
