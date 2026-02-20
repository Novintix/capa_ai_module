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
    # DO #6: All scores validated to be in range 1-10 (guard state transitions)
    HF: int = Field(..., ge=1, le=10, description="Historical Frequency (1-10)")
    TR: int = Field(..., ge=1, le=10, description="Trend Analysis (1-10)")
    PS: int = Field(..., ge=1, le=10, description="Process Stability (1-10)")
    PC: int = Field(..., ge=1, le=10, description="Preventive Controls (1-10)")
    DM: int = Field(..., ge=1, le=10, description="Detection/Monitoring (1-10)")
    SY: int = Field(..., ge=1, le=10, description="Systemic vs Isolated (1-10)")
    OE: int = Field(..., ge=1, le=10, description="Operator/Equipment (1-10)")
    CA: int = Field(..., ge=1, le=10, description="CAPA Effectiveness (1-10)")
    SU: int = Field(..., ge=1, le=10, description="Supplier Factors (1-10)")
    AU: int = Field(..., ge=1, le=10, description="Audit Findings (1-10)")
    reasoning: str = Field(..., description="Explanation for the scores")

class OccurrenceOutput(BaseModel):
    weighted_score: int
    rating: str
    breakdown: OccurrenceScoreResponse

class OccurrenceState(BaseModel):
    input: ComplaintData
    # DO #1: Iteration counter — always included, initialized to 0
    iteration: int = 0
    # Intermediate: pre-computed evidence per parameter (set by prepare_evidence node)
    # DON'T #7: No hidden state — all intermediate data declared here
    evidence_summary: Optional[Dict[str, str]] = None
    # Intermediate output from LLM
    raw_scores: Optional[OccurrenceScoreResponse] = None
    # Final output
    final_output: Optional[OccurrenceOutput] = None


