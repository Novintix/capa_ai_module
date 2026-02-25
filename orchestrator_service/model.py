from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any


class SimilarCase(BaseModel):
    complaint_id: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None


class RiskRequest(BaseModel):
    # Core identifier
    complaint_id: str = Field(..., description="Unique complaint identifier")

    # Primary description — maps to severity 'issue', occurrence/detection 'description'
    complaint_description: str = Field(..., description="Full complaint description")

    # Occurrence + Detection fields
    source: str = Field(..., description="Source of complaint e.g. Customer, Supplier Audit")
    date: str = Field(..., description="Date of complaint e.g. 2024-01-15")
    product: str = Field(..., description="Product name/model involved")
    additional_context: str = Field(default="", description="Any extra context")
    similar_cases: List[SimilarCase] = Field(default_factory=list, description="Similar historical cases")

    # Optional metadata for conflict detection / orchestrator logic
    structured_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Optional session tracking
    thread_id: Optional[str] = None
    user_id: Optional[str] = Field(default="default_user", description="Identifier for the user/tenant")
    policy_path: Optional[str] = Field(None, description="Path to policy document for detection")


class AgentResponseModel(BaseModel):
    score: int
    confidence: float
    reasoning: str


class RiskResponse(BaseModel):
    severity_score: Optional[int] = None
    occurrence_score: Optional[int] = None
    detection_score: Optional[int] = None
    rpn_value: Optional[int] = None
    workflow_status: str
    escalation_required: bool = False
    escalation_reason: Optional[str] = None
    conflict_detected: bool = False
    errors: Optional[List[str]] = None
    agent_outputs: Optional[Dict[str, Any]] = None
