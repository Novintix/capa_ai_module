"""
FastAPI router for unified RCA v2.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException

from .agent_v2 import RootCauseAnalysisCoordinatorV2
from .schemas_v2 import (
    RCAFishboneSelectionInputV2,
    RCAHealthResponseV2,
    RCAResponseV2,
    RCAStartInputV2,
    RCAWhyDecisionInputV2,
)


RCA_V2_TIMEOUT_SECONDS = int(os.getenv("RCA_V2_TIMEOUT_SECONDS", "300"))

router = APIRouter(prefix="/root-cause-analysis/v2", tags=["root-cause-analysis-v2"])

_coordinator_v2: RootCauseAnalysisCoordinatorV2 | None = None


def _get_coordinator_v2() -> RootCauseAnalysisCoordinatorV2:
    global _coordinator_v2
    if _coordinator_v2 is None:
        _coordinator_v2 = RootCauseAnalysisCoordinatorV2()
    return _coordinator_v2


@router.post(
    "/start",
    response_model=RCAResponseV2,
    summary="Start unified RCA v2 (method=fishbone|why)",
)
async def start_v2(input_data: RCAStartInputV2):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_get_coordinator_v2().start_v2, input_data),
            timeout=RCA_V2_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="RCA v2 start timed out. Retry or check status endpoint if session was created.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RCA v2 start failed: {exc}") from exc


@router.post(
    "/resume/fishbone-selection",
    response_model=RCAResponseV2,
    summary="Resume RCA v2 after fishbone cause selection",
)
async def resume_fishbone_selection_v2(input_data: RCAFishboneSelectionInputV2):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_get_coordinator_v2().resume_fishbone_selection_v2, input_data),
            timeout=RCA_V2_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Fishbone resume timed out.") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fishbone resume failed: {exc}") from exc


@router.post(
    "/resume/why-decision",
    response_model=RCAResponseV2,
    summary="Resume RCA v2 after Why decision (continue|root_cause)",
)
async def resume_why_decision_v2(input_data: RCAWhyDecisionInputV2):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_get_coordinator_v2().resume_why_decision_v2, input_data),
            timeout=RCA_V2_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Why resume timed out.") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Why resume failed: {exc}") from exc


@router.get("/status/{session_id}", response_model=RCAResponseV2)
async def status_v2(session_id: str):
    try:
        return _get_coordinator_v2().status_v2(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RCA v2 status failed: {exc}") from exc


@router.get("/health", response_model=RCAHealthResponseV2)
def health_v2():
    return {"status": "healthy", "service": "Unified Root Cause Analysis v2"}
