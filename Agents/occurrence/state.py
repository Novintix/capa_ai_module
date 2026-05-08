from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class PatternData(BaseModel):
    complaint_id: str
    trend_score: int
    trend_category: str
    confidence: float
    matched_complaint_ids: List[str]
    identified_pattern: str
    explanation: str
    error: Optional[str] = None

class SimilarCaseMatch(BaseModel):
    recordId: Optional[str] = None
    complaintId: Optional[str] = None
    dateReceived: Optional[str] = None
    source: Optional[str] = None
    regionCountry: Optional[str] = None
    severity: Optional[str] = None
    productFamily: Optional[str] = None
    site: Optional[str] = None
    descriptionOfIssue: Optional[str] = None
    status: Optional[str] = None
    daysOpen: Optional[int] = None
    assignedTo: Optional[str] = None
    isNc: Optional[bool] = None
    ncId: Optional[str] = None
    fieldAction: Optional[str] = None
    euReportable: Optional[bool] = None
    fdaReportable: Optional[bool] = None
    capaNeeded: Optional[bool] = None
    capaId: Optional[str] = None
    capaRationale: Optional[str] = None
    repeated: Optional[bool] = None
    workflowStage: Optional[str] = None
    similarity: float

class SimilarCasesData(BaseModel):
    query: str
    similarityThreshold: float
    similarCount: int
    message: str
    topMatches: List[SimilarCaseMatch]

class ComplaintData(BaseModel):
    # Core complaint info - always required
    complaint_id: str
    description: str
    source: str
    date: str
    product: str
    
    # New structured inputs - pattern and similar cases analysis
    pattern_data: Optional[PatternData] = Field(None, description="Pattern analysis results")
    similar_cases_data: Optional[SimilarCasesData] = Field(None, description="Similar cases analysis results")
    
    # Legacy support for backward compatibility
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list, description="List of similar past cases (legacy format)")
    additional_context: Optional[str] = Field(None, description="Context about controls, detection, etc.")
    metrics_data: Optional[str] = Field(None, description="JSON string of metrics definition (loaded from metrics.json, Excel, PDF, etc.)")

class OccurrenceScoreResponse(BaseModel):
    # Dynamic parameter scores - can handle any parameter set
    scores: Dict[str, int] = Field(..., description="Parameter scores (1-10) with parameter codes as keys")
    reasoning: str = Field(..., description="Explanation for the scores")
    
    def __getattr__(self, name):
        """Allow accessing scores as attributes for backward compatibility"""
        if name in self.scores:
            return self.scores[name]
        # Provide defaults for legacy parameter access
        legacy_defaults = {
            'HF': 1, 'TR': 1, 'PS': 1, 'PC': 1, 'DM': 1,
            'SY': 1, 'OE': 1, 'CA': 1, 'SU': 1, 'AU': 1
        }
        if name in legacy_defaults:
            return legacy_defaults[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

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


