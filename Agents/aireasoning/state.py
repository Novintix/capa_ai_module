from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class AIReasoningInput(BaseModel):
    complaint_id: str
    risk_score: int = Field(..., ge=1, le=100, description="Overall risk score (1-100)")
    pattern: str = Field(..., description="Pattern identified from occurrence analysis")
    severity_level: str = Field(..., description="Severity level (e.g., Critical, High, Medium, Low)")
    nc_source: str = Field(..., description="Non-conformance source")
    regulatory_impact: str = Field(..., description="Regulatory impact description")
    customer_impact: str = Field(..., description="Customer impact description")
    additional_context: Optional[str] = Field(None, description="Additional context or notes")
    
    # Generic additional data - accepts any key-value pairs
    additional_data: Optional[Dict[str, Any]] = Field(None, description="Any additional dynamic data fields")

class AIReasoningResponse(BaseModel):
    reasoning: str = Field(..., description="AI-generated reasoning for the risk assessment")
    key_factors: list[str] = Field(..., description="Key factors contributing to the assessment")
    recommendations: list[str] = Field(..., description="Recommended actions")
    confidence_level: str = Field(..., description="Confidence level: High, Medium, Low")


class AIReasoningState(BaseModel):
    input: AIReasoningInput
    iteration: int = 0
    evidence_summary: Optional[str] = None
    raw_reasoning: Optional[AIReasoningResponse] = None
    final_output: Optional[AIReasoningResponse] = None
