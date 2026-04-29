"""
orchestrator_service/router.py

FastAPI router for the O2 Risk Analysis Orchestrator.

Endpoints:
    POST  /capa/analyze               — run full analysis, return complete report
    POST  /capa/correct/{thread_id}   — submit corrected input after validation failure
    GET   /capa/status/{thread_id}    — lightweight status check
    GET   /capa/state/{thread_id}     — full state snapshot
    POST  /capa/resume/{thread_id}    — resume paused/crashed workflow

Response design:
    /analyze always returns the FULL result synchronously — no polling needed.
    The orchestrator runs to completion inside the request and the complete
    final_report is returned in the same response body.

    Status values returned:
      "completed"            → full final_report included in response
      "awaiting_correction"  → input failed validation (soft), correction_message explains why
      "rejected"             → malicious input, hard terminated, no retry
      "error"                → unexpected exception
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .orchestrator import orchestrator_graph, redis_client, MAX_CORRECTION_ATTEMPTS
from agent_ops import agentops_session

router = APIRouter(prefix="/capa", tags=["CAPA Risk Analysis"])


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ══════════════════════════════════════════════════════════════════════════════

class EnrichedInput(BaseModel):
    """
    Structured complaint fields provided directly by the UI from MongoDB data.
    When present, the orchestrator skips the full LLM context extraction and
    maps these fields straight into the `extracted` dict, saving one LLM call.
    Only urgency and death_or_injury are still inferred via a lightweight LLM check.

    All fields are optional — any missing field falls back to the raw_input text.
    Field names mirror the EXTRACTION_PROMPT enriched output exactly.
    """
    core_issue:           Optional[str] = Field(None, description="Concise 1-sentence issue description")
    complaint_id:         Optional[str] = Field(None, description="Business complaint ID e.g. CP-9902")
    product:              Optional[str] = Field(None, description="Product name / identifier")
    product_type:         Optional[str] = Field(None, description="Product type / category")
    date:                 Optional[str] = Field(None, description="Date of complaint / awareness")
    source:               Optional[str] = Field(None, description="Complaint source e.g. Customer, Internal")
    market_country:       Optional[str] = Field(None, description="Market / country of origin")
    severity_hint:        Optional[str] = Field(None, description="Severity level: Critical/High/Medium/Low")
    issue_type:           Optional[str] = Field(None, description="Issue category e.g. Hardware Failure")
    regulatory_standards: Optional[list] = Field(None, description="Applicable standards e.g. ['ISO 13485']")
    suspected_cause:      Optional[str] = Field(None, description="Preliminary suspected cause")
    urgency_reason:       Optional[str] = Field(None, description="Reason for urgency if applicable")
    region:               Optional[str] = Field(None, description="Geographic region")
    batch_number:         Optional[str] = Field(None, description="Batch / lot number if known")


class CAPARequest(BaseModel):
    raw_input:      Optional[str]  = Field(None,
                                   description=(
                                       "Free-text complaint description. "
                                       "Optional when enriched_input is provided — "
                                       "core_issue is used as the validation text in that case."
                                   ))
    thread_id:      Optional[str]  = Field(None,
                                   description="Optional thread ID — auto-generated if not supplied")
    enriched_input: Optional[EnrichedInput] = Field(None,
                                   description=(
                                       "Structured complaint fields from the UI/MongoDB. "
                                       "When provided, raw_input is not required — core_issue "
                                       "is used for validation and the LLM extraction step is skipped."
                                   ))


class CorrectionRequest(BaseModel):
    corrected_input: str = Field(..., min_length=10,
                                 description="The corrected complaint description")


class ResumeRequest(BaseModel):
    correction: Optional[dict] = Field(None,
                                  description="Optional state patch to inject before resuming")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _read_state_from_redis(thread_id: str) -> Optional[dict]:
    """
    Reads latest checkpoint state for thread_id directly from Redis.
    No RedisSearch (FT.SEARCH) required.
    """
    pattern  = f"checkpoint_latest:{thread_id}:*"
    ptr_keys = redis_client.keys(pattern)

    if not ptr_keys:
        return None

    nodes_found  = []
    merged_state = {}

    for ptr_key in ptr_keys:
        ptr_key_str = ptr_key.decode("utf-8") if isinstance(ptr_key, bytes) else ptr_key
        parts       = ptr_key_str.split(":")
        node_name   = parts[2] if len(parts) > 2 else "unknown"
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

    return {
        "nodes_completed": sorted(set(nodes_found)),
        "state":           merged_state,
    }


def _derive_status(state: dict, nodes_completed: list) -> str:
    if state.get("final_report"):
        return "completed"
    if state.get("awaiting_correction"):
        return "awaiting_correction"
    if state.get("validation_passed") is False and not state.get("awaiting_correction"):
        return "rejected"
    if nodes_completed:
        return "in_progress"
    return "unknown"


def _build_full_response(thread_id: str, result: dict) -> dict:
    """
    Builds the complete response body from an orchestrator invoke result.
    Called by /analyze and /correct after a successful synchronous invoke.

    Returns one of:
      - completed response with full final_report
      - awaiting_correction response with correction details
      - rejected response with reason
    """

    # ── Awaiting correction (soft fail — user can retry) ──────────────────────
    correction_response = result.get("correction_response")
    if correction_response:
        return {
            "thread_id": thread_id,
            **correction_response,
        }

    # ── Hard rejection (malicious or terminated) ──────────────────────────────
    if result.get("validation_passed") is False and not result.get("awaiting_correction"):
        return {
            "thread_id":           thread_id,
            "status":              "rejected",
            "reason":              result.get("validation_error", "Input rejected."),
            "validation_category": result.get("validation_category"),
        }

    # ── Completed — return full report ────────────────────────────────────────
    final_report = result.get("final_report", {})
    rpn          = final_report.get("rpn", {})

    return {
        "thread_id":    thread_id,
        "complaint_id": result.get("complaint_id"),
        "status":       "completed",

        # ── Top-level RPN summary for quick access ────────────────────────────
        "rpn": {
            "severity_score":   rpn.get("severity_score"),
            "severity_label":   rpn.get("severity_label"),
            "occurrence_score": rpn.get("occurrence_score"),
            "detection_score":  rpn.get("detection_score"),
            "rpn_value":        rpn.get("rpn_value"),
            "rpn_level":        rpn.get("rpn_level"),
        },

        # ── Per-agent summaries ───────────────────────────────────────────────
        "agent_summaries": final_report.get("agent_summaries", {}),

        # ── Regulatory output ─────────────────────────────────────────────────
        "regulatory": final_report.get("regulatory", {}),

        # ── AI reasoning output ───────────────────────────────────────────────
        "reasoning": final_report.get("reasoning", {}),

        # ── Execution Log ─────────────────────────────────────────────────────
        "node_log":     result.get("node_log", []),

        # ── Full report for completeness ──────────────────────────────────────
        "final_report": final_report,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /capa/analyze
#
# Runs the full orchestrator synchronously and returns the complete result.
#
# Response shapes:
#   status: "completed"            → full final_report, rpn, agent_summaries,
#                                    regulatory, reasoning all in response body
#   status: "awaiting_correction"  → validation failed (soft), correction_message
#                                    tells user what to fix, use /capa/correct
#   status: "rejected"             → malicious input, hard terminated
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze")
@agentops_session(name="Risk_Analysis", tags=["capa_ai_module", "risk_analysis", "orchestrator"])
async def analyze(request: CAPARequest):
    """
    Submit a complaint for full synchronous risk analysis.

    Runs the complete orchestrator pipeline and returns the full result
    in a single response — no polling required.

    The orchestrator runs:
      input_validator → context_node → payload_builder_node
        → [A5|A1|A2|A3] parallel → A4 occurrence → rpn_calculator
        → A6 regulatory → A7 reasoning → finalize_node

    On completion returns status: "completed" with full final_report.
    On validation failure returns status: "awaiting_correction".
    On malicious input returns status: "rejected".
    """
    thread_id = request.thread_id or f"capa-{uuid.uuid4().hex[:12]}"
    config    = _config(thread_id)

    import json as _json
    print("\n" + "="*60)
    print("[/capa/analyze] Incoming payload:")
    print(_json.dumps(request.model_dump(exclude_none=True), indent=2))
    print("="*60 + "\n")

    # Resolve the text used for validation + LLM extraction.
    # Priority: explicit raw_input → enriched_input.core_issue → error
    raw_input = request.raw_input
    if not raw_input and request.enriched_input:
        raw_input = request.enriched_input.core_issue
    if not raw_input:
        raise HTTPException(
            status_code=422,
            detail="Provide either raw_input or enriched_input.core_issue."
        )

    # Build initial state — include enriched_input if the UI provided it
    initial_state = {
        "thread_id":        thread_id,
        "raw_input":        raw_input,
        "agent_results":    [],
        "node_log":         [],
        "errors":           [],
        "correction_count": 0,
    }
    if request.enriched_input:
        initial_state["enriched_input"] = request.enriched_input.model_dump(exclude_none=True)

    try:
        result = orchestrator_graph.invoke(initial_state, config=config)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": str(exc), "thread_id": thread_id}
        )

    return _build_full_response(thread_id, result)


# ══════════════════════════════════════════════════════════════════════════════
# POST /capa/correct/{thread_id}
#
# Submit corrected input after receiving awaiting_correction response.
# Returns same shape as /analyze — full report on success.
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/correct/{thread_id}")
@agentops_session(name="Risk_Analysis_Correction", tags=["capa_ai_module", "risk_analysis", "correction"])
async def correct_input(thread_id: str, body: CorrectionRequest):
    """
    Submit corrected input after a validation failure.

    1. Verifies the workflow exists and is awaiting correction.
    2. Patches raw_input + resets correction flags in state.
    3. Re-runs from input_validator with correction_count preserved.
    4. Returns same response shape as /analyze.
    """
    config = _config(thread_id)

    # ── Verify thread exists ──────────────────────────────────────────────────
    state_data = _read_state_from_redis(thread_id)
    if not state_data:
        raise HTTPException(
            status_code=404,
            detail={
                "error":     f"No workflow found for thread_id: {thread_id}.",
                "hint":      "Use POST /capa/analyze to start a new analysis.",
                "thread_id": thread_id,
            }
        )

    current_state = state_data.get("state", {})

    # ── Verify it is awaiting correction ─────────────────────────────────────
    if not current_state.get("awaiting_correction"):
        status = _derive_status(current_state, state_data.get("nodes_completed", []))
        raise HTTPException(
            status_code=400,
            detail={
                "error":     "This workflow is not awaiting correction.",
                "thread_id": thread_id,
                "status":    status,
                "hint":      (
                    "Use POST /capa/analyze to start a new analysis, or "
                    "GET /capa/status/{thread_id} to check current state."
                ),
            }
        )

    try:
        orchestrator_graph.update_state(
            config,
            {
                "raw_input":           body.corrected_input,
                "awaiting_correction": False,
                "correction_response": None,
                "correction_message":  None,
            },
            as_node="input_validator",
        )

        result = orchestrator_graph.invoke(None, config=config)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": str(exc), "thread_id": thread_id}
        )

    return _build_full_response(thread_id, result)


# ══════════════════════════════════════════════════════════════════════════════
# GET /capa/status/{thread_id}
#
# Lightweight status check — useful for monitoring long-running workflows
# or checking state of a background job started externally.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{thread_id}")
async def get_status(thread_id: str):
    """
    Lightweight status check for any workflow by thread_id.

    Status values:
      completed            → final_report available, use /capa/state for full data
      awaiting_correction  → input validation failed, correction required
      rejected             → malicious input, hard terminated
      in_progress          → analysis running (background job)
      unknown              → state not yet populated
    """
    result = _read_state_from_redis(thread_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No workflow found for thread_id: {thread_id}"
        )

    state           = result.get("state", {})
    nodes_completed = result.get("nodes_completed", [])
    status          = _derive_status(state, nodes_completed)

    response = {
        "thread_id":       thread_id,
        "complaint_id":    state.get("complaint_id"),
        "status":          status,
        "nodes_completed": nodes_completed,
        "rpn_value":       state.get("rpn_value"),
        "rpn_level":       state.get("rpn_level"),
        "errors":          state.get("errors", []),
    }

    if status == "awaiting_correction":
        correction_response = state.get("correction_response") or {}
        response["correction"] = {
            "correction_message":  correction_response.get("correction_message")
                                   or state.get("correction_message"),
            "validation_error":    correction_response.get("validation_error")
                                   or state.get("validation_error"),
            "validation_category": correction_response.get("validation_category")
                                   or state.get("validation_category"),
            "attempts_used":       correction_response.get("attempts_used")
                                   or state.get("correction_count", 1),
            "attempts_remaining":  correction_response.get("attempts_remaining")
                                   or (MAX_CORRECTION_ATTEMPTS - state.get("correction_count", 1)),
            "hint": correction_response.get("hint", (
                "Provide a medical device issue description. "
                "Use POST /capa/correct/{thread_id} to resubmit."
            )),
        }

    if status == "rejected":
        response["reason"]              = state.get("validation_error")
        response["validation_category"] = state.get("validation_category")

    if status == "completed":
        response["rpn"] = {
            "severity_score":   state.get("severity_score"),
            "occurrence_score": state.get("occurrence_score"),
            "detection_score":  state.get("detection_score"),
            "rpn_value":        state.get("rpn_value"),
            "rpn_level":        state.get("rpn_level"),
        }

    return response


# ══════════════════════════════════════════════════════════════════════════════
# GET /capa/state/{thread_id}
#
# Full state snapshot — returns everything including final_report, node_log,
# agent summaries. Use for debugging or Streamlit display.
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """
    Full state snapshot for any workflow by thread_id.
    Returns all nodes completed, full final report, node log, RPN, and errors.
    """
    result = _read_state_from_redis(thread_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No state found for thread_id: {thread_id}. "
                "Either the analysis has not been started or the thread_id is wrong."
            )
        )

    state           = result.get("state", {})
    nodes_completed = result.get("nodes_completed", [])
    status          = _derive_status(state, nodes_completed)

    response = {
        "thread_id":    thread_id,
        "complaint_id": state.get("complaint_id"),
        "status":       status,
        "nodes_completed": nodes_completed,
        "rpn": {
            "severity_score":   state.get("severity_score"),
            "occurrence_score": state.get("occurrence_score"),
            "detection_score":  state.get("detection_score"),
            "rpn_value":        state.get("rpn_value"),
            "rpn_level":        state.get("rpn_level"),
        },
        "final_report": state.get("final_report"),
        "node_log":     state.get("node_log", []),
        "errors":       state.get("errors", []),
    }

    if status == "awaiting_correction":
        response["correction"] = state.get("correction_response") or {
            "correction_message":  state.get("correction_message"),
            "validation_error":    state.get("validation_error"),
            "validation_category": state.get("validation_category"),
            "attempts_used":       state.get("correction_count", 1),
            "attempts_remaining":  MAX_CORRECTION_ATTEMPTS - state.get("correction_count", 1),
        }

    if status == "rejected":
        response["reason"]              = state.get("validation_error")
        response["validation_category"] = state.get("validation_category")

    return response


# ══════════════════════════════════════════════════════════════════════════════
# POST /capa/resume/{thread_id}
#
# Resume a paused or crashed workflow from last Redis checkpoint.
# Returns full result same as /analyze.
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/resume/{thread_id}")
@agentops_session(name="Risk_Analysis_Resume", tags=["capa_ai_module", "risk_analysis", "resume"])
async def resume(thread_id: str, body: ResumeRequest = ResumeRequest()):
    """
    Resume a paused or crashed workflow from last Redis checkpoint.

    - If correction dict provided → patches state before resuming.
    - Completed nodes are NOT repeated.
    - Returns full result same as /analyze on completion.
    """
    config = _config(thread_id)

    try:
        if body.correction:
            orchestrator_graph.update_state(config, body.correction)

        result = orchestrator_graph.invoke(None, config=config)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": str(exc), "thread_id": thread_id}
        )

    return _build_full_response(thread_id, result)

from .orchestrator import deep_serialize, _now as _ts_now

@router.websocket("/events/{thread_id}")
async def event_stream(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    print(f"WS connected: {thread_id}")
    try:
        initial = _read_state_from_redis(thread_id)
        if initial:
            await websocket.send_json({
                "type": "initial_state",
                "data": {
                    "nodes_completed": initial.get("nodes_completed", []),
                    "status": _derive_status(initial.get("state", {}), initial.get("nodes_completed", []))
                }
            })
        while True:
            msg = await websocket.receive_json()
            cmd = msg.get("command")
            if cmd == "start":
                raw_input = msg.get("raw_input", "")
                if not raw_input:
                    await websocket.send_json({"type": "error", "message": "Missing raw_input"})
                    continue
                config = _config(thread_id)
                await websocket.send_json({"type": "status", "status": "started"})
                try:
                    async for event in orchestrator_graph.astream_events(
                        {"raw_input": raw_input, "agent_results": [], "node_log": [], "errors": [], "correction_count": 0},
                        config=config, version="v2"
                    ):
                        kind = event["event"]
                        name = event["name"]
                        metadata = event.get("metadata", {})
                        
                        # Is this event related to a top-level node in our graph?
                        is_node = (metadata.get("langgraph_node") == name and name != "__start__")
                        
                        if kind == "on_chain_start" and name == "LangGraph":
                            await websocket.send_json({"type": "graph_start"})
                        elif kind == "on_chain_start" and is_node:
                            await websocket.send_json({"type": "node_start", "node": name, "timestamp": _ts_now()})
                        elif kind == "on_chain_end" and is_node:
                            out = event["data"].get("output")
                            await websocket.send_json({"type": "node_end", "node": name, "data": deep_serialize(out) if out else None, "timestamp": _ts_now()})
                        elif kind == "on_chain_end" and name == "LangGraph":
                            final_out = event["data"].get("output")
                            await websocket.send_json({"type": "completed", "data": _build_full_response(thread_id, final_out) if final_out else {}})
                except Exception as exc:
                    import traceback
                    print(traceback.format_exc()) # Log full traceback to backend terminal
                    await websocket.send_json({
                        "type": "error", 
                        "message": f"Graph Execution Error: {str(exc) or 'Internal Failure'}"
                    })
            elif cmd == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        print(f"WS disconnected: {thread_id}")
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
