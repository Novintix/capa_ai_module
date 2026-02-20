"""
Why Question Agent — API Router
Handles all why-question-related endpoints.
"""

from fastapi import APIRouter, HTTPException

from .schemas import StartWhyInput, ContinueWhyInput, WhyQuestionOutput, WhyQuestionError, WhyChainHistoryOutput, WhyChainEntry
from .logger import log_api_request, log_api_response, log_error
from .agent import WhyQuestionAgent


# ---------------------------------------------------------------------------
# Router setup
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/why", tags=["why-question"])

# Lazy singleton — initialized on first request
_why_agent: WhyQuestionAgent = None


def _get_agent() -> WhyQuestionAgent:
    """Return the singleton WhyQuestionAgent, creating it if necessary."""
    global _why_agent
    if _why_agent is None:
        _why_agent = WhyQuestionAgent()
    return _why_agent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=WhyQuestionOutput)
def start_why_chain(input_data: StartWhyInput):
    """
    Start a new 5 Whys chain for a complaint.

    Provide full context on this first call:
    - **complaint_id** : Unique identifier (used as the Redis session key).
    - **complaint**    : The original problem statement.
    - **evidence**     : Supporting facts, measurements, or observations.
    - **sop**          : The relevant Standard Operating Procedure or work instruction.

    All context is stored in Redis (TTL 7 days).
    Returns the first "Why?" question.
    """
    try:
        agent = _get_agent()
        log_api_request("/why/start", complaint_id=input_data.complaint_id, why_depth=1)

        result = agent.start(input_data)

        if result.get("error") or not result.get("why_question"):
            detail = result.get("error") or "Why question generation failed with no details."
            log_error("router /why/start", detail)
            log_api_response("/why/start", complaint_id=input_data.complaint_id, why_depth=0, success=False)
            raise HTTPException(status_code=422, detail=detail)

        log_api_response("/why/start", complaint_id=input_data.complaint_id, why_depth=result["why_depth"], success=True)
        return WhyQuestionOutput(
            complaint_id=result["complaint_id"],
            why_question=result["why_question"],
            reasoning=result["reasoning"],
            why_depth=result["why_depth"]
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_error("router /why/start", str(exc))
        log_api_response("/why/start", complaint_id=input_data.complaint_id, why_depth=0, success=False)
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


@router.post("/continue", response_model=WhyQuestionOutput)
def continue_why_chain(input_data: ContinueWhyInput):
    """
    Continue an existing 5 Whys chain with the answer to the last Why question.

    Only two fields are needed:
    - **complaint_id** : Must match the one used in /why/start.
    - **answer**       : Your answer to the previously generated Why question.

    All other context (complaint, evidence, SOP, prior chain) is loaded from Redis.
    Returns the next "Why?" question.
    """
    try:
        agent = _get_agent()
        log_api_request("/why/continue", complaint_id=input_data.complaint_id)

        result = agent.continue_chain(input_data)

        if result.get("error") or not result.get("why_question"):
            detail = result.get("error") or "Why question generation failed with no details."
            log_error("router /why/continue", detail)
            log_api_response("/why/continue", complaint_id=input_data.complaint_id, why_depth=0, success=False)
            raise HTTPException(status_code=422, detail=detail)

        log_api_response("/why/continue", complaint_id=input_data.complaint_id, why_depth=result["why_depth"], success=True)
        return WhyQuestionOutput(
            complaint_id=result["complaint_id"],
            why_question=result["why_question"],
            reasoning=result["reasoning"],
            why_depth=result["why_depth"]
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_error("router /why/continue", str(exc))
        log_api_response("/why/continue", complaint_id=input_data.complaint_id, why_depth=0, success=False)
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


@router.get("/health")
def health_check():
    """Health check for the Why Question Agent."""
    return {
        "status": "healthy",
        "agent": "Why Question Agent",
        "description": "Generates the next 'Why?' question for 5 Whys root cause analysis."
    }


@router.get("/history/{complaint_id}", response_model=WhyChainHistoryOutput)
def get_why_history(complaint_id: str):
    """
    Retrieve the full Why Q&A history for a complaint.

    Returns every Why question that has been generated for this complaint,
    paired with the answer that was provided (or null if still pending).

    - **complaint_id** : The ID used when calling /why/start.
    """
    try:
        agent = _get_agent()
        history = agent.get_history(complaint_id)

        return WhyChainHistoryOutput(
            complaint_id=history["complaint_id"],
            complaint=history["complaint"],
            total_whys=history["total_whys"],
            chain=[
                WhyChainEntry(
                    depth=entry["depth"],
                    question=entry["question"],
                    answer=entry["answer"]
                )
                for entry in history["chain"]
            ]
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        log_error("router /why/history", str(exc))
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc