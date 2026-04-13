"""
FastAPI Router for Fishbone v3 Orchestrator
"""

from fastapi import APIRouter, HTTPException, Depends
from .schemas import FishboneV3Input, FishboneV3Output, FishboneV3DecisionInput
from .agent import FishboneOrchestratorV3
from .logger import log_error

router = APIRouter(prefix="/fishbone-v3", tags=["Fishbone V3 (HITL)"])

# Singleton orchestrator
orchestrator = FishboneOrchestratorV3()


@router.post("/analyze", response_model=FishboneV3Output)
async def analyze_complaint(input_data: FishboneV3Input):
    """
    Phase 1: Run Fishbone analysis and pause for human review.
    Returns categorized and validated causes.
    """
    try:
        result = orchestrator.analyze(input_data)
        if "error" in result and result["status"] == "ERROR":
            error_msg = result["error"]
            # Map guardrail errors to 400
            if "Invalid" in error_msg:
                raise HTTPException(status_code=400, detail=error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /analyze", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decide", response_model=FishboneV3Output)
async def submit_decisions(decision_input: FishboneV3DecisionInput):
    """
    Phase 2: Submit human decisions (RCA, PROCEED) for the causes.
    Completes the analysis and returns final labeled results.
    """
    try:
        result = orchestrator.submit_decisions(decision_input)
        if "error" in result and result["status"] == "ERROR":
            error_msg = result["error"]
            # Map specific guardrail/session errors
            if "expired" in error_msg.lower() or "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            if "Integrity" in error_msg or "Invalid" in error_msg:
                raise HTTPException(status_code=400, detail=error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /decide", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for Fishbone V3"""
    return {"status": "healthy", "service": "Fishbone V3 Orchestrator"}
