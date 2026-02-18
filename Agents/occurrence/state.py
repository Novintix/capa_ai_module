from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ComplaintData(BaseModel):
    complaint_id: str
    description: str
    source: str
    date: str
    product: str
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list, description="List of similar past cases with dates and details")
    additional_context: Optional[str] = Field(None, description="Context about controls, detection, etc.")
    metrics_data: Optional[str] = Field(None, description="JSON string of metrics definition (loaded from metrics.json, Excel, PDF, etc.)")

class OccurrenceScoreResponse(BaseModel):
    HF: int = Field(..., description="Historical Frequency (1-10)")
    TR: int = Field(..., description="Trend Analysis (1-10)")
    PS: int = Field(..., description="Process Stability (1-10)")
    PC: int = Field(..., description="Preventive Controls (1-10)")
    DM: int = Field(..., description="Detection/Monitoring (1-10)")
    SY: int = Field(..., description="Systemic vs Isolated (1-10)")
    OE: int = Field(..., description="Operator/Equipment (1-10)")
    CA: int = Field(..., description="CAPA Effectiveness (1-10)")
    SU: int = Field(..., description="Supplier Factors (1-10)")
    AU: int = Field(..., description="Audit Findings (1-10)")
    
    # Reasoning
    reasoning: str = Field(..., description="Explanation for the scores")

class OccurrenceOutput(BaseModel):
    weighted_score: float
    rating: str
    breakdown: OccurrenceScoreResponse

class OccurrenceState(BaseModel):
    input: ComplaintData
    # Intermediate output from LLM
    raw_scores: Optional[OccurrenceScoreResponse] = None
    # Final output
    final_output: Optional[OccurrenceOutput] = None
