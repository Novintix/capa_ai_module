"""
FastAPI router for Root Cause Analysis coordinator.

3 parent-level HITL endpoints:
  POST /rca/start               (HITL #1) — user picks method: why | fishbone
  POST /rca/select-category     (HITL #2) — fishbone path: user picks a category
  POST /rca/proceed-action-plan (HITL #3) — user confirms proceeding to action plan

Child-orchestrator internal HITL is handled by their own routes:
  POST /fishbone-v3/decide               (fishbone cause decisions)
  POST /why-analysis-v3/human-review     (why cause selection)
"""

import asyncio
import os
import time
import uuid

from fastapi import APIRouter, HTTPException

from .agent import RootCauseAnalysisCoordinator
from .schemas import (
    RCAHealthResponse,
    RCAProceedActionPlanInput,
    RCAResponse,
    RCASelectCategoryInput,
    RCAStartInput,
)

RCA_TIMEOUT_SECONDS = int(os.getenv("RCA_TIMEOUT_SECONDS", "300"))

router = APIRouter(prefix="/rca", tags=["root-cause-analysis"])

_coordinator: RootCauseAnalysisCoordinator | None = None


def _get_coordinator() -> RootCauseAnalysisCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = RootCauseAnalysisCoordinator()
    return _coordinator


def _timeout_response(complaint_id: str, session_id: str) -> dict:
    """Build a partial response when the request times out."""
    return {
        "complaint_id": complaint_id,
        "session_id": session_id,
        "phase": "processing",
        "message": (
            "Analysis is still running in the background. "
            f"Poll GET /rca/status/{complaint_id}?session_id={session_id} for updates."
        ),
        "available_categories": [],
        "action_plan_ready": False,
        "next_action": "poll_status",
        "updated_at": time.time(),
    }


# ── HITL #1 ───────────────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=RCAResponse,
    summary="HITL #1 — Choose RCA method and start analysis",
    description=(
        "User selects 'why' or 'fishbone' and submits complaint details.\n\n"
        "**why path**: Why Analysis starts immediately. "
        "Internal cause-selection HITL is handled via `POST /why-analysis-v3/human-review`. "
        "Call `POST /rca/proceed-action-plan` when finished.\n\n"
        "**fishbone path**: Fishbone Analysis starts. "
        "Internal cause-decision HITL is handled via `POST /fishbone-v3/decide`. "
        "Call `POST /rca/select-category` when Fishbone + decisions are done."
    ),
    responses={400: {"description": "Invalid input"}, 500: {"description": "Internal error"}},
)
async def start(input_data: RCAStartInput):
    coordinator = _get_coordinator()
    session_id = f"{input_data.complaint_id}_{uuid.uuid4().hex[:8]}"
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(coordinator.start, input_data, session_id),
            timeout=RCA_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        return _timeout_response(input_data.complaint_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RCA start failed: {exc}") from exc


# ── HITL #2 ───────────────────────────────────────────────────────────────────

@router.post(
    "/select-category",
    response_model=RCAResponse,
    summary="HITL #2 (fishbone path) — Pick a category to continue with Why Analysis",
    description=(
        "After Fishbone Analysis and cause decisions (`/fishbone-v3/decide`) are complete, "
        "user selects which fishbone category to investigate further with Why Analysis.\n\n"
        "Why Analysis then starts. Internal cause-selection HITL is handled via "
        "`POST /why-analysis-v3/human-review`. "
        "Call `POST /rca/proceed-action-plan` when Why Analysis is finished."
    ),
    responses={
        400: {"description": "Invalid category or wrong phase"},
        404: {"description": "Session not found"},
        500: {"description": "Internal error"},
    },
)
async def select_category(input_data: RCASelectCategoryInput):
    coordinator = _get_coordinator()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(coordinator.select_category_and_start_why, input_data),
            timeout=RCA_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        return _timeout_response(input_data.complaint_id, input_data.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RCA select-category failed: {exc}") from exc


# ── HITL #3 ───────────────────────────────────────────────────────────────────

@router.post(
    "/proceed-action-plan",
    response_model=RCAResponse,
    summary="HITL #3 — Confirm or reject proceeding to Action Plan",
    description=(
        "After Why Analysis (including its internal HITL via `/why-analysis-v3/human-review`) "
        "is complete, user decides whether to proceed to the Action Plan."
    ),
    responses={
        400: {"description": "Wrong phase"},
        404: {"description": "Session not found"},
        500: {"description": "Internal error"},
    },
)
async def proceed_action_plan(input_data: RCAProceedActionPlanInput):
    coordinator = _get_coordinator()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(coordinator.proceed_to_action_plan, input_data),
            timeout=RCA_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        return _timeout_response(input_data.complaint_id, input_data.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RCA proceed-action-plan failed: {exc}") from exc


# ── Status / Health ───────────────────────────────────────────────────────────

@router.get(
    "/status/{complaint_id}",
    response_model=RCAResponse,
    responses={404: {"description": "Session not found"}, 500: {"description": "Internal error"}},
)
async def status(complaint_id: str, session_id: str | None = None):
    try:
        return _get_coordinator().status(complaint_id, session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RCA status failed: {exc}") from exc


@router.get("/health", response_model=RCAHealthResponse)
def health():
    return {"status": "healthy", "service": "Root Cause Analysis Coordinator"}
