from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class MatchResult(BaseModel):
    """A single similar complaint match with all key fields."""
    recordId: Optional[str] = None
    complaintId: Optional[str] = None
    dateReceived: Optional[datetime] = None
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
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score (0-1)")


class SimilarCasesInput(BaseModel):
    """Input schema for similar cases search."""
    query: str = Field(
        ...,
        min_length=5,
        description="Complaint description text to search for similar cases",
        examples=["Device overheating during normal use with burn marks on casing"]
    )


class SimilarCasesOutput(BaseModel):
    """Output schema for similar cases search results."""
    query: str = Field(..., description="Original complaint description from user")
    similarityThreshold: float = Field(..., description="Minimum similarity score used")
    similarCount: int = Field(..., description="Total number of complaints above threshold")
    message: str = Field(..., description="Human-readable summary of results")
    topMatches: List[MatchResult] = Field(default_factory=list, description="All matching complaints above threshold")


class SimilarCasesState(BaseModel):
    """State that flows through the LangGraph nodes."""
    input: SimilarCasesInput
    query_embedding: Optional[List[float]] = None
    all_similar: Optional[List[Dict[str, Any]]] = None
    final_output: Optional[SimilarCasesOutput] = None
    iteration: int = 0
    error: Optional[str] = None
