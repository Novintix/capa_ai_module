"""
Zero Evidence Agent API Router
Handles all zero_evidence endpoints.
"""

from fastapi import APIRouter, HTTPException

from .schemas import ZeroEvidenceInput, ZeroEvidenceResult, SelectedRootCause
from .logger import log_api_request, log_api_response
from .agent import ZeroEvidenceAgent


# Create API router
router = APIRouter(prefix="/zero-evidence", tags=["zero-evidence"])

# Lazy initialization of agent
_zero_evidence_agent = None


def get_zero_evidence_agent():
    """Get or initialize the Zero Evidence Agent (lazy initialization)"""
    global _zero_evidence_agent
    if _zero_evidence_agent is None:
        _zero_evidence_agent = ZeroEvidenceAgent()
    return _zero_evidence_agent


@router.post("/", response_model=ZeroEvidenceResult)
def run_zero_evidence_analysis(input_data: ZeroEvidenceInput):
    """
    Run Zero Evidence Mode analysis.

    This endpoint is called when:
    - No validation evidence exists
    - No observable signals exist
    - No historical similar cases are available

    The agent selects the **Most Critical Functional Cause** from the
    provided cause list using first-principles reasoning and criticality scoring.

    Scoring formula:
        score = (0.4 * severity)
              + (0.2 * single_point_failure_score)
              + (0.2 * system_dependency_score)
              + (0.2 * safety_impact_score)

    Args:
        input_data: ZeroEvidenceInput from the cause generation agent

    Returns:
        ZeroEvidenceResult with the single selected most critical root cause
    """
    try:
        agent = get_zero_evidence_agent()

        # Log request
        log_api_request("/zero-evidence", input_data.question_id)

        # Run analysis
        result = agent.analyze(input_data)

        # Check for error in result
        if result.get("error") or result.get("selected_root_cause") is None:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Zero Evidence Agent failed to select a cause")
            )

        # Log response
        log_api_response(
            input_data.question_id,
            result["selected_root_cause"]["cause_id"]
        )

        # Build Pydantic response
        selected = result["selected_root_cause"]
        return ZeroEvidenceResult(
            mode=result["mode"],
            selected_root_cause=SelectedRootCause(
                cause_id=selected["cause_id"],
                cause_text=selected["cause_text"],
                process_step=selected["process_step"],
                reason=selected["reason"],
            ),
            confidence=result.get("confidence", "MEDIUM"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running Zero Evidence analysis: {str(e)}"
        )


@router.get("/health")
def zero_evidence_health():
    """Zero Evidence Agent health check"""
    agent = get_zero_evidence_agent()
    return {
        "status": "healthy",
        "agent": "zero_evidence",
        "mode": "ZERO_EVIDENCE_MODE",
        "agent_initialized": agent is not None,
    }
