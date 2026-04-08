"""
Schemas for Why Analysis V2 orchestrator.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WhyAnalysisV2Input(BaseModel):
    """Input contract for Why Analysis V2."""

    complaint_id: str = Field(..., description="Unique complaint or CAPA ID")
    complaint: str = Field(..., description="Original complaint description")
    evidence: Optional[str] = Field(default="", description="Evidence summary text")
    sop: Optional[str] = Field(default="", description="Relevant SOP text")
    fmea_document_path: Optional[str] = Field(
        default=None,
        description="Optional FMEA path used by cause generation",
    )
    max_loops: Optional[int] = Field(default=10, ge=1, le=20)
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for Redis checkpointing and resumption. Auto-generated if not supplied.",
    )

    # Structured evidence fields for validation agent
    evidence_files: Optional[List[str]] = Field(default=None)
    logs: Optional[Any] = Field(default=None)
    reports: Optional[Any] = Field(default=None)
    process_data: Optional[Any] = Field(default=None)
    historical_capa: Optional[Any] = Field(default=None)
    policies: Optional[Any] = Field(default=None)
    investigation_records: Optional[Any] = Field(default=None)
    supporting_system_information: Optional[Any] = Field(default=None)


class RootCauseDetail(BaseModel):
    """Final selected root cause details."""

    cause_id: str
    cause_text: str
    process_step: str
    failure_mode: Optional[str] = None
    potential_effects: Optional[str] = None
    severity: Optional[int] = None
    occurrence: Optional[int] = None
    detection: Optional[int] = None
    current_controls: Optional[str] = None
    source: str = "unknown"
    reason: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    selection_path: str


class WhyChainItem(BaseModel):
    """One loop item in the why chain."""

    loop: int
    question: str
    selected_cause: str
    selected_cause_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    selection_path: str
    loop_decision: Optional[str] = None
    loop_reasoning: Optional[str] = None


class WhyAnalysisV2Output(BaseModel):
    """Output contract for Why Analysis V2."""

    complaint_id: str
    status: str
    mode: str
    analysis_depth: int
    max_loops: int

    ai_flagged: bool = False
    manual_investigation_required: bool = False
    stopping_reason: Optional[str] = None

    root_cause: Optional[RootCauseDetail] = None
    why_chain: List[WhyChainItem] = Field(default_factory=list)
    iteration_outputs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Full per-iteration outputs for each agent in flow order",
    )

    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    loop_control_summary: Dict[str, Any] = Field(default_factory=dict)

    execution_time_seconds: Optional[float] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
