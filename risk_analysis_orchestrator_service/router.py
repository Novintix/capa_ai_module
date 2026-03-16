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
import json
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .orchestrator import orchestrator_graph, redis_client

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
# HELPER — read state directly from Redis keys
# Avoids FT.SEARCH (RedisSearch module) — works with plain Redis.
# LangGraph stores state under keys like:
#   checkpoint_latest:{thread_id}:{node_name}:{uuid}
# ══════════════════════════════════════════════════════════════════════════════

def _read_state_from_redis(thread_id: str) -> Optional[dict]:
    """
    Reads the latest checkpoint state for a thread_id directly from Redis.

    LangGraph RedisSaver stores in two steps:
      1. checkpoint_latest:{thread_id}:{channel}:{run_id}  — plain string POINTER
         → value is the actual checkpoint key name
      2. checkpoint:{thread_id}:{channel}:{run_id}:{cp_id} — ReJSON-RL document
         → contains checkpoint.channel_values with the real state data

    Reads pointers with r.get(), then dereferences with r.json().get().
    No RedisSearch (FT.SEARCH) needed.
    """
    pattern = f"checkpoint_latest:{thread_id}:*"
    ptr_keys = redis_client.keys(pattern)

    if not ptr_keys:
        return None

    nodes_found = []
    merged_state = {}

    for ptr_key in ptr_keys:
        # Decode the pointer key to extract node name
        ptr_key_str = ptr_key.decode("utf-8") if isinstance(ptr_key, bytes) else ptr_key
        parts = ptr_key_str.split(":")
        # Format: checkpoint_latest:{thread_id}:{node_name}:{run_id}
        node_name = parts[2] if len(parts) > 2 else "unknown"
        nodes_found.append(node_name)

        # Read the pointer value (plain string pointing to the real checkpoint key)
        ptr_val = redis_client.get(ptr_key)
        if not ptr_val:
            continue
        checkpoint_key = ptr_val.decode("utf-8") if isinstance(ptr_val, bytes) else ptr_val

        # Read the actual checkpoint JSON document using JSON.GET
        try:
            doc = redis_client.json().get(checkpoint_key)
            if doc and isinstance(doc, dict):
                channel_values = doc.get("checkpoint", {}).get("channel_values", {})
                if channel_values:
                    merged_state.update(channel_values)
        except Exception:
            pass  # Skip unreadable checkpoint

    return {
        "nodes_completed": sorted(set(nodes_found)),
        "state": merged_state,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /capa/analyze
# Starts a new risk analysis workflow.
# Generates thread_id if not provided.
# Returns final_report on completion.
# Returns validation error cleanly if input fails validator node.
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze", status_code=202)
async def analyze(request: CAPARequest, background_tasks: BackgroundTasks):
    """
    Submit a free-text complaint for risk analysis.

    - thread_id is auto-generated if not provided.
    - Returns 202 immediately.
    - Analysis runs in the background.
    - Polling /capa/state/{thread_id} is used to track progress.
    """
    thread_id = request.thread_id or f"capa-{uuid.uuid4().hex[:12]}"
    config    = _config(thread_id)

    # Function to run in the background
    def run_analysis():
        try:
            orchestrator_graph.invoke(
                {
                    "raw_input":     request.raw_input,
                    "agent_results": [],
                    "node_log":      [],
                    "errors":        [],
                },
                config=config,
            )
        except Exception as e:
            # We log but the response is already sent
            print(f"❌ Background analysis failed for {thread_id}: {str(e)}")

    background_tasks.add_task(run_analysis)

    return {
        "thread_id": thread_id,
        "status":    "accepted",
        "message":   "Analysis started in background"
    }




# ══════════════════════════════════════════════════════════════════════════════
# GET /capa/state/{thread_id}
# Returns full state snapshot at any point.
# Use after crash, after HITL pause, or for debugging.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """
    Inspect the full state of any workflow by thread_id.
    Reads directly from Redis keys — no RedisSearch required.

    Returns:
        - All nodes completed so far
        - Full decoded state values
        - Final report if workflow is complete
    """
    result = _read_state_from_redis(thread_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No state found for thread_id: {thread_id}. "
                   f"Either the analysis hasn't been started or the thread_id is wrong."
        )

    state = result.get("state", {})

    # Derive status from what's in state
    if state.get("final_report"):
        status = "completed"
    elif state.get("validation_passed") is False:
        status = "validation_failed"
    elif result["nodes_completed"]:
        status = "in_progress_or_completed"
    else:
        status = "unknown"

    return {
        "thread_id":       thread_id,
        "status":          status,
        "nodes_completed": result["nodes_completed"],
        "rpn": {
            "severity_score":   state.get("severity_score"),
            "occurrence_score": state.get("occurrence_score"),
            "detection_score":  state.get("detection_score"),
            "rpn_value":        state.get("rpn_value"),
            "rpn_level":        state.get("rpn_level"),
        },
        "final_report":    state.get("final_report"),
        "node_log":        state.get("node_log", []),
        "errors":          state.get("errors", []),
    }


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
    Reads directly from Redis keys — no RedisSearch required.

    Returns:
        thread_id, status, rpn_value, rpn_level, nodes_completed
    """
    result = _read_state_from_redis(thread_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No workflow found for thread_id: {thread_id}"
        )

    state = result.get("state", {})

    if state.get("final_report"):
        status = "completed"
    elif state.get("validation_passed") is False:
        status = "validation_failed"
    elif result["nodes_completed"]:
        status = "in_progress_or_completed"
    else:
        status = "unknown"

    return {
        "thread_id":       thread_id,
        "status":          status,
        "nodes_completed": result["nodes_completed"],
        "rpn_value":       state.get("rpn_value"),
        "rpn_level":       state.get("rpn_level"),
        "errors":          state.get("errors", []),
    }


# _derive_status removed — state is now read directly from Redis keys
# using _read_state_from_redis() which does not require RedisSearch module.
