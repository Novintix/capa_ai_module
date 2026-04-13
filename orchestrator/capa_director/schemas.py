from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class CAPADirectorInput(BaseModel):
    complaint_id:   str       = Field(...,         description="Unique CAPA identifier")
    complaint:      str       = Field(...,         description="Complaint description")
    evidence:       Optional[str] = Field(default="",   description="Supporting evidence")
    sop:            Optional[str] = Field(default="",   description="Relevant SOP")
    fmea_document_path: Optional[str] = Field(default=None)
    thread_id:      Optional[str] = Field(default=None, description="Resume existing thread")
    max_rca_depth:  Optional[int] = Field(default=5)

    containment_actions: Optional[str] = Field(default="Standard containment initiated")
    timeline_constraint: Optional[str] = Field(default="30 days")
    available_resources: Optional[str] = Field(default="Engineering, Quality, Production")
    system_context:      Optional[str] = Field(default="Manufacturing Plant")

    skip_human_review: bool = Field(default=False, description="True = fully automated")


class HumanReviewInput(BaseModel):
    thread_id: str            = Field(...,          description="Thread to resume")
    approved:  bool           = Field(...,          description="True=proceed, False=reject")
    feedback:  Optional[str]  = Field(default=None, description="Reviewer notes")


class CAPADirectorOutput(BaseModel):
    thread_id:                Optional[str] = None
    complaint_id:             str
    risk_analysis:            Optional[Dict[str, Any]] = None
    rca_analysis:             Optional[Dict[str, Any]] = None
    action_plan:              Optional[Dict[str, Any]] = None
    effectiveness_evaluation: Optional[Dict[str, Any]] = None
    status:                   str = "completed"
    error:                    Optional[str] = None

    # Director visibility fields
    director_reasoning:  Optional[str] = None   # Why O1 made its last decision
    awaiting_human:      bool = False
    current_node:        Optional[str] = None   # Which node is paused
    rca_retry_count:     int = 0
    plan_retry_count:    int = 0