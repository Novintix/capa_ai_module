"""
router.py

FastAPI router that exposes the O2 Risk Analysis Orchestrator as an API.

Endpoints:
    POST   /capa/analyze          — start a new risk analysis
    GET    /capa/state/{thread_id} — inspect state of any workflow
    POST   /capa/resume/{thread_id} — resume a paused/interrupted workflow
    GET    /capa/status/{thread_id} — quick status check
"""

import uuid
from typing import Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .orchestrator import orchestrator_graph

router = APIRouter(prefix="/capa", tags=["CAPA Risk Analysis"])


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class CAPARequest(BaseModel):
    raw_input:  str            = Field(..., min_length=10,
                                description="Free-text engineer complaint")
    thread_id:  Optional[str]  = Field(None,
                                description="Optional — provide to resume or correlate. "
                                            "Auto-generated if not supplied.")


class CAPAResponse(BaseModel):
    thread_id:    str
    status:       str
    final_report: Optional[dict] = None
    error:        Optional[str]  = None


class ResumeRequest(BaseModel):
    correction: Optional[dict] = Field(None,
                                 description="Optional state patch to inject before resuming")


# ══════════════════════════════════════════════════════════════════════════════
# HELPER — build config
# thread_id is the Redis checkpoint key.
# Every invoke, get_state, update_state needs the same config.
# ══════════════════════════════════════════════════════════════════════════════

def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


# ══════════════════════════════════════════════════════════════════════════════
# POST /capa/analyze
# Starts a new risk analysis workflow.
# Generates thread_id if not provided.
# Returns final_report on completion.
# Returns validation error cleanly if input fails validator node.
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze", response_model=CAPAResponse)
async def analyze(request: CAPARequest):
    """
    Submit a free-text complaint for risk analysis.

    - thread_id is auto-generated if not provided.
    - Pass thread_id back in subsequent calls to inspect or resume.
    - State is checkpointed to Redis after every node.
    """
    # Use provided thread_id or generate a new unique one
    thread_id = request.thread_id or f"capa-{uuid.uuid4().hex[:12]}"
    config    = _config(thread_id)

    try:
        result = orchestrator_graph.invoke(
            {
                "raw_input":     request.raw_input,
                "agent_results": [],     # initialise reducer field
                "node_log":      [],     # initialise audit reducer
                "errors":        [],     # initialise error reducer
            },
            config=config,
        )

        # Validation failed inside input_validator node
        if not result.get("validation_passed", True):
            return CAPAResponse(
                thread_id = thread_id,
                status    = "validation_failed",
                error     = result.get("validation_error",
                                       "Input validation failed"),
            )

        # Normal completion
        return CAPAResponse(
            thread_id    = thread_id,
            status       = "completed",
            final_report = result.get("final_report"),
        )

    except Exception as exc:
        # Unexpected error — state is already checkpointed in Redis
        # Client can inspect via GET /capa/state/{thread_id}
        raise HTTPException(
            status_code = 500,
            detail      = {
                "error":     str(exc),
                "thread_id": thread_id,
                "hint":      "State is checkpointed. "
                             "Use GET /capa/state/{thread_id} to inspect."
            }
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /capa/state/{thread_id}
# Returns full state snapshot at any point.
# Use after crash, after HITL pause, or for debugging.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """
    Inspect the full state of any workflow by thread_id.

    Returns:
        - All state fields at last checkpoint
        - Which node runs next (if workflow is paused)
        - Full node_log audit trail
        - Any errors recorded
    """
    try:
        config        = _config(thread_id)
        state_snapshot = orchestrator_graph.get_state(config)

        if state_snapshot is None:
            raise HTTPException(
                status_code = 404,
                detail      = f"No state found for thread_id: {thread_id}"
            )

        return {
            "thread_id":   thread_id,
            "next_node":   list(state_snapshot.next) if state_snapshot.next else [],
            "values":      dict(state_snapshot.values),
            "status":      _derive_status(state_snapshot),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# POST /capa/resume/{thread_id}
# Resumes a paused or interrupted workflow.
# Optionally injects human corrections before resuming.
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/resume/{thread_id}", response_model=CAPAResponse)
async def resume(thread_id: str, body: ResumeRequest = ResumeRequest()):
    """
    Resume a paused or crashed workflow.

    - Reads last checkpoint from Redis automatically.
    - If correction dict is provided — patches state before resuming.
    - Resumes from the next pending node.
    - Completed nodes are NOT repeated.

    Use cases:
        - Server crashed mid-execution → resume from last checkpoint
        - Human-in-the-loop review → inject correction, then resume
        - Low confidence flagged → human corrects agent_results, resumes
    """
    config = _config(thread_id)

    try:
        # If human provided corrections — patch state before resuming
        if body.correction:
            orchestrator_graph.update_state(
                config,
                body.correction,
            )

        # invoke(None) = do not start fresh — read checkpoint from Redis
        result = orchestrator_graph.invoke(None, config=config)

        return CAPAResponse(
            thread_id    = thread_id,
            status       = "completed",
            final_report = result.get("final_report"),
        )

    except Exception as exc:
        raise HTTPException(
            status_code = 500,
            detail      = {
                "error":     str(exc),
                "thread_id": thread_id,
            }
        )


# ══════════════════════════════════════════════════════════════════════════════
# GET /capa/status/{thread_id}
# Quick status check — lighter than full state inspection.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{thread_id}")
async def get_status(thread_id: str):
    """
    Quick status check for a workflow.

    Returns:
        thread_id, status, rpn_value, rpn_level, next_node
    """
    try:
        config         = _config(thread_id)
        state_snapshot = orchestrator_graph.get_state(config)

        if state_snapshot is None:
            raise HTTPException(
                status_code = 404,
                detail      = f"No workflow found for thread_id: {thread_id}"
            )

        values = dict(state_snapshot.values)

        return {
            "thread_id":  thread_id,
            "status":     _derive_status(state_snapshot),
            "next_node":  list(state_snapshot.next) if state_snapshot.next else [],
            "rpn_value":  values.get("rpn_value"),
            "rpn_level":  values.get("rpn_level"),
            "errors":     values.get("errors", []),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# HELPER — derive human-readable status from state snapshot
# ══════════════════════════════════════════════════════════════════════════════

def _derive_status(state_snapshot: Any) -> str:
    """
    Derives a simple status string from the LangGraph state snapshot.
    """
    values = dict(state_snapshot.values)

    # Validation failed
    if values.get("validation_passed") is False:
        return "validation_failed"

    # Final report exists — workflow completed
    if values.get("final_report"):
        return "completed"

    # Workflow is paused — next node is waiting
    if state_snapshot.next:
        return "paused"

    # No next node and no final report — unexpected
    return "unknown"