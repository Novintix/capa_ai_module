"""
Cause Generation Agent Schemas
Input/Output data models
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class QuestionInput(BaseModel):
    """Input question for cause generation"""
    question_id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="Why question (e.g., 'Why did the bike stop?', 'Why is tablet strength incorrect?')")
    context: Optional[str] = Field(None, description="Additional context or previous cause from 5-Why analysis")
    evidence_context: Optional[dict] = Field(None, description="Evidence, logs, reports for cause extraction")


class Cause(BaseModel):
    """Single cause from FMEA"""
    cause_id: str = Field(..., description="Unique cause identifier")
    cause_text: str = Field(..., description="Cause description from FMEA")
    process_step: str = Field(..., description="Associated process step")
    failure_mode: str = Field(..., description="Associated failure mode")
    potential_effects: Optional[str] = Field(None, description="Potential effects")
    severity: Optional[int] = Field(None, description="Severity rating from FMEA")
    occurrence: Optional[int] = Field(None, description="Occurrence rating from FMEA")
    detection: Optional[int] = Field(None, description="Detection rating from FMEA")
    current_controls: Optional[str] = Field(None, description="Current process controls")
    source: str = Field(default="FMEA", description="Source of cause (FMEA/Expanded)")


class CauseGenerationResult(BaseModel):
    """Output result with list of all possible causes"""
    question_id: str = Field(..., description="Question identifier")
    question: str = Field(..., description="Original why question")
    causes: List[Cause] = Field(..., description="List of all possible causes")
    total_causes: int = Field(..., description="Total number of causes identified")
    fmea_document_used: str = Field(..., description="Path to FMEA document used")
    matched_entries: int = Field(..., description="Number of FMEA entries matched")
    confidence: float = Field(..., description="Confidence in matching (0-1)")
    notes: Optional[str] = Field(None, description="Additional notes or warnings")
