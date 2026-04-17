"""
Pydantic schemas for Root Cause Analysis coordinator.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RCACommonInput(BaseModel):
    complaint_id: str = Field(..., description="Unique complaint identifier")
    complaint: str = Field(..., description="Complaint or issue description")
    evidence: str = Field(default="", description="Optional evidence text")
    sop: str = Field(default="", description="Optional SOP context")
    fmea_document_path: Optional[str] = Field(default=None)

    evidence_files: Optional[List[str]] = Field(default=None)
    logs: Optional[Any] = Field(default=None)
    reports: Optional[Any] = Field(default=None)
    process_data: Optional[Any] = Field(default=None)
    historical_capa: Optional[Any] = Field(default=None)
    policies: Optional[Any] = Field(default=None)
    investigation_records: Optional[Any] = Field(default=None)
    supporting_system_information: Optional[Any] = Field(default=None)


# ── HITL #1: User picks method and starts analysis ──────────────────────────

class RCAStartInput(RCACommonInput):
    """
    HITL #1 — User selects RCA method and starts the analysis.

    method="why"      → Runs Why Analysis directly. Internal HITL (cause selection)
                        is handled via POST /why-analysis-v3/human-review.
                        Call POST /rca/proceed-action-plan when Why is done.

    method="fishbone" → Runs Fishbone Analysis. Internal HITL (cause decisions)
                        is handled via POST /fishbone-v3/decide.
                        Call POST /rca/select-category when Fishbone is done.
    """
    method: Literal["why", "fishbone"] = Field(
        ..., description="RCA method to use: 'why' or 'fishbone'"
    )


# ── HITL #2: User picks a fishbone category to continue with Why Analysis ───

class RCASelectCategoryInput(BaseModel):
    """
    HITL #2 (fishbone path only) — After Fishbone analysis + cause decisions are
    complete, user selects a specific cause to investigate with Why Analysis.
    """
    complaint_id: str = Field(..., description="Complaint identifier")
    category: Optional[str] = Field(default=None, description="Fishbone category (derived from cause if omitted)")
    selected_cause_id: Optional[str] = Field(default=None, description="ID of the specific cause to investigate")
    selected_cause_text: Optional[str] = Field(default=None, description="Text of the specific cause to investigate")
    session_id: str = Field(
        ...,
        description="Session ID from /rca/start response.",
    )


# ── HITL #3: User confirms to proceed to Action Plan ────────────────────────

class RCAProceedActionPlanInput(BaseModel):
    """
    HITL #3 — After Why Analysis is done, user decides whether to proceed
    to the Action Plan.
    """
    complaint_id: str = Field(..., description="Complaint identifier")
    confirmed: bool = Field(default=True, description="User confirmed proceed to action plan")
    session_id: str = Field(
        ...,
        description="Session ID from /rca/start response.",
    )


# ── Response ─────────────────────────────────────────────────────────────────

class RCAResponse(BaseModel):
    complaint_id: str
    session_id: Optional[str] = None
    phase: str
    selected_method: Optional[str] = None
    message: Optional[str] = None

    # Fishbone data
    available_categories: List[str] = Field(default_factory=list)
    selected_category: Optional[str] = None
    fishbone_output: Optional[Dict[str, Any]] = None

    # Why data
    why_output: Optional[Dict[str, Any]] = None
    why_session_id: Optional[str] = None

    # Final handoff
    action_plan_ready: bool = False
    action_plan_endpoint: Optional[str] = None

    next_action: Optional[str] = None
    error: Optional[str] = None
    updated_at: float


class RCAHealthResponse(BaseModel):
    status: str
    service: str
