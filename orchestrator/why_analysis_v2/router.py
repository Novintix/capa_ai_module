"""
FastAPI router for Why Analysis V2 orchestrator.
"""

from fastapi import APIRouter, HTTPException

from .agent import WhyAnalysisV2Orchestrator
from .logger import log_api_request, log_api_response, log_error
from .orchestrator import _read_state_from_redis, orchestrator_graph
from .schemas import WhyAnalysisV2Input, WhyAnalysisV2Output


router = APIRouter(prefix="/why-analysis-v2", tags=["why-analysis-v2-orchestrator"])

_orchestrator: WhyAnalysisV2Orchestrator | None = None


def _get_orchestrator() -> WhyAnalysisV2Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WhyAnalysisV2Orchestrator()
    return _orchestrator


@router.post("/", response_model=WhyAnalysisV2Output)
def run_why_analysis_v2(input_data: WhyAnalysisV2Input):
    """Run Why Analysis V2 using JSON input."""
    try:
        log_api_request("/why-analysis-v2", input_data.complaint_id)

        result = _get_orchestrator().analyze(input_data)

        log_api_response(
            complaint_id=input_data.complaint_id,
            status=result.get("status", "error"),
            stopping_reason=result.get("stopping_reason"),
        )

        return WhyAnalysisV2Output(**result)

    except HTTPException:
        raise
    except Exception as exc:
        log_error("router /why-analysis-v2", str(exc))
        raise HTTPException(status_code=500, detail=f"Error running Why Analysis V2: {exc}")


@router.get("/status/{session_id}")
def why_analysis_v2_status(session_id: str):
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
        "stopping_reason": state.get("stopping_reason"),
        "node_log": state.get("node_log", []),
        "errors": state.get("errors", []),
    }


@router.get("/state/{session_id}")
def why_analysis_v2_state(session_id: str):
    """Return full checkpoint state for a session stored in Redis."""
    result = _read_state_from_redis(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found in Redis")
    state = result.get("state", {})
    return {
        "session_id": session_id,
        "status": state.get("status"),
        "final_output": state.get("final_output"),
        "node_log": state.get("node_log", []),
        "errors": state.get("errors", []),
        "current_loop_count": state.get("current_loop_count", 0),
        "stopping_reason": state.get("stopping_reason"),
    }


@router.post("/resume/{session_id}")
def why_analysis_v2_resume(session_id: str):
    """Resume a previously checkpointed Why Analysis V2 session."""
    result = _read_state_from_redis(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found in Redis")
    try:
        config = {"configurable": {"thread_id": session_id}}
        resumed = orchestrator_graph.invoke(None, config=config)
        output = resumed.get("final_output") or {}
        return WhyAnalysisV2Output(**output) if output else {"session_id": session_id, "status": "resumed"}
    except Exception as exc:
        log_error("resume", str(exc))
        raise HTTPException(status_code=500, detail=f"Resume failed: {exc}")


@router.get("/health")
def why_analysis_v2_health():
    """Health endpoint for Why Analysis V2."""
    return {
        "status": "healthy",
        "agent": "why_analysis_v2_orchestrator",
        "description": "Question -> Cause Generation -> Validation -> Loop Control with conditional ranking and zero evidence terminal mode",
        "flow": [
            "question",
            "cause_generation",
            "validation",
            "ranking_if_multi_validated",
            "loop_control",
            "continue_or_stop",
        ],
        "zero_validated_branch": "zero_evidence_mode_then_stop_ai_flagged",
        "default_max_loops": 10,
    }
