"""
Pydantic schemas for unified RCA v2.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RCACommonInputV2(BaseModel):
    complaint_id: str = Field(..., description="Unique complaint identifier")
    complaint: str = Field(..., description="Complaint or issue description")
    evidence: str = Field(default="", description="Optional evidence text")
    sop: str = Field(default="", description="Optional SOP context")
    fmea_document_path: Optional[str] = Field(default=None, description="Optional FMEA file path")

    evidence_files: Optional[List[str]] = Field(default=None)
    logs: Optional[Any] = Field(default=None)
    reports: Optional[Any] = Field(default=None)
    process_data: Optional[Any] = Field(default=None)
    historical_capa: Optional[Any] = Field(default=None)
    policies: Optional[Any] = Field(default=None)
    investigation_records: Optional[Any] = Field(default=None)
    supporting_system_information: Optional[Any] = Field(default=None)


class RCAStartInputV2(RCACommonInputV2):
    method: Literal["why", "fishbone"] = Field(
        ..., description="Start RCA with Why directly or with Fishbone first"
    )


class RCAFishboneSelectionInputV2(BaseModel):
    session_id: str = Field(..., description="RCA v2 session id from start response")
    complaint_id: Optional[str] = Field(default=None, description="Optional for audit")
    selected_cause_id: str = Field(..., description="Selected fishbone cause id to enter Why flow")


class RCAWhyDecisionInputV2(BaseModel):
    session_id: str = Field(..., description="RCA v2 session id from start response")
    complaint_id: Optional[str] = Field(default=None, description="Optional for audit")
    selected_cause_id: str = Field(..., description="Selected qualified cause id from current Why level")
    decision: Literal["continue", "root_cause"] = Field(
        ..., description="continue to next Why level or confirm root cause"
    )


class RCAResponseV2(BaseModel):
    complaint_id: str
    session_id: str
    method: Optional[str] = None

    status: str
    phase: str
    message: Optional[str] = None
    next_action: Optional[str] = None
    awaiting_human_review: bool = False
    hitl_type: Optional[str] = None

    ai_flagged: bool = False
    stopping_reason: Optional[str] = None
    error: Optional[str] = None

    root_cause: Optional[Dict[str, Any]] = None

    fishbone: Dict[str, Any] = Field(default_factory=dict)
    why: Dict[str, Any] = Field(default_factory=dict)
    agent_payloads: Dict[str, Any] = Field(default_factory=dict)

    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    node_log: List[Dict[str, Any]] = Field(default_factory=list)
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)

    updated_at: float
    execution_time_seconds: Optional[float] = None


class RCAHealthResponseV2(BaseModel):
    status: str
    service: str
