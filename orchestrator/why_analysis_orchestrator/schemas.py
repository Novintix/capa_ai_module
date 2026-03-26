"""
Why Analysis Orchestrator Schemas
Input/Output models with comprehensive iteration tracking
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

class WhyAnalysisInput(BaseModel):
    """
    Input schema for Why Analysis Orchestrator
    
    Required fields define the problem context
    Optional fields control analysis behavior
    """
    complaint_id: str = Field(
        ...,
        description="Unique identifier for the CAPA/complaint record"
    )
    complaint: str = Field(
        ...,
        description="The original problem statement or complaint description"
    )
    evidence: Optional[str] = Field(
        default="",
        description="Supporting facts, observations, measurements, or data"
    )
    sop: Optional[str] = Field(
        default="",
        description="Standard Operating Procedure or work instruction relevant to the problem"
    )
    fmea_document_path: Optional[str] = Field(
        default=None,
        description=(
            "Path to FMEA Excel document. "
            "If provided: FMEA iterative mode (loops until causes exhausted). "
            "If omitted: No-FMEA single-shot mode (LLM generates causes once)."
        )
    )
    max_depth: Optional[int] = Field(
        default=5,
        description="Maximum number of Why iterations to perform (default: 5)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "CAPA-2026-001",
                "complaint": "Syringe marking was incorrect during production",
                "fmea_document_path": "fmea.xlsx"
            }
        }


# =============================================================================
# ITERATION TRACKING SCHEMAS
# =============================================================================

class CauseDetail(BaseModel):
    """Detailed information about a single cause"""
    cause_id: str = Field(..., description="Unique identifier for the cause")
    cause_text: str = Field(..., description="Description of the cause")
    process_step: str = Field(..., description="Process step where cause occurs")
    failure_mode: Optional[str] = Field(None, description="Type of failure")
    potential_effects: Optional[str] = Field(None, description="Potential impact")
    severity: Optional[int] = Field(None, description="Severity score (1-10)")
    occurrence: Optional[int] = Field(None, description="Occurrence score (1-10)")
    detection: Optional[int] = Field(None, description="Detection score (1-10)")
    current_controls: Optional[str] = Field(None, description="Current control measures")
    source: str = Field(..., description="Source of cause (FMEA or LLM_Generated)")


class WhyIterationDetail(BaseModel):
    """Comprehensive details of a single Why iteration"""
    depth: int = Field(..., description="Iteration depth (1 = first Why)")
    question: str = Field(..., description="The Why question asked")
    reasoning: str = Field(..., description="Reasoning for this question")
    causes_found: int = Field(..., description="Number of causes generated/matched")
    causes: List[CauseDetail] = Field(default_factory=list, description="All causes found")
    selected_cause: Optional[CauseDetail] = Field(None, description="Cause selected as most critical")
    fmea_matches: int = Field(default=0, description="Number of FMEA entries matched")
    generation_method: str = Field(..., description="How causes were generated (FMEA/LLM_Generated)")


class RootCauseDetail(BaseModel):
    """Final selected root cause with complete context"""
    cause_id: str = Field(..., description="Identifier of the root cause")
    cause_text: str = Field(..., description="Description of the root cause")
    process_step: str = Field(..., description="Process step of the root cause")
    failure_mode: Optional[str] = Field(None, description="Type of failure")
    potential_effects: Optional[str] = Field(None, description="Potential impact")
    severity: Optional[int] = Field(None, description="Severity score")
    occurrence: Optional[int] = Field(None, description="Occurrence score")
    detection: Optional[int] = Field(None, description="Detection score")
    current_controls: Optional[str] = Field(None, description="Current control measures")
    source: str = Field(..., description="Source (FMEA or LLM_Generated)")
    reason: str = Field(..., description="Reasoning for selection as root cause")
    confidence_score: Optional[float] = Field(None, description="Confidence in selection (0.0-1.0)")


# =============================================================================
# OUTPUT SCHEMAS
# =============================================================================

class WhyAnalysisOutput(BaseModel):
    """
    Output schema with comprehensive iteration tracking
    
    Provides complete visibility into the analysis process for UI display
    """
    complaint_id: str = Field(..., description="The complaint ID analyzed")
    
    root_cause: Optional[RootCauseDetail] = Field(
        None,
        description="The final selected root cause (None if analysis failed)"
    )
    
    confidence: str = Field(
        ...,
        description="Overall confidence level: LOW, MEDIUM, or HIGH"
    )
    
    mode: str = Field(
        ...,
        description="Analysis mode used: FMEA_ITERATIVE, NO_FMEA_SINGLE_SHOT, or ERROR"
    )
    
    analysis_depth: int = Field(
        ...,
        description="Total number of Why iterations completed"
    )
    
    why_iterations: List[WhyIterationDetail] = Field(
        default_factory=list,
        description="Detailed information for each Why iteration"
    )
    
    total_causes_analyzed: int = Field(
        default=0,
        description="Total number of causes analyzed across all iterations"
    )
    
    fmea_document_used: Optional[str] = Field(
        None,
        description="Path to FMEA document used (if any)"
    )
    
    execution_time_seconds: Optional[float] = Field(
        None,
        description="Total execution time in seconds"
    )
    
    stopping_reason: Optional[str] = Field(
        None,
        description="Reason why the analysis stopped (completed, no_causes_found, cause_repetition_detected, max_depth_reached, etc.)"
    )
    
    error: Optional[str] = Field(
        None,
        description="Error message if analysis failed or partially failed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "CAPA-2026-001",
                "root_cause": {
                    "cause_id": "C002",
                    "cause_text": "Ink adhesion failure due to incorrect curing temperature",
                    "process_step": "Syringe Marking (Graduation & Text)",
                    "failure_mode": "Faded / incorrect / misaligned markings",
                    "potential_effects": "Dosage misinterpretation, medication error to patient",
                    "severity": 9,
                    "occurrence": 4,
                    "detection": 6,
                    "current_controls": "Vision inspection system, ink adhesion validation",
                    "source": "FMEA",
                    "reason": "Highest criticality score (8.4) - high severity and safety risk",
                    "confidence_score": 0.85
                },
                "confidence": "HIGH",
                "mode": "FMEA_ITERATIVE",
                "analysis_depth": 3,
                "why_iterations": [
                    {
                        "depth": 1,
                        "question": "Why was the syringe marking incorrect?",
                        "reasoning": "Initial question based on complaint",
                        "causes_found": 4,
                        "causes": [],
                        "selected_cause": {
                            "cause_id": "C002",
                            "cause_text": "Ink adhesion failure",
                            "process_step": "Syringe Marking",
                            "source": "FMEA"
                        },
                        "fmea_matches": 4,
                        "generation_method": "FMEA"
                    }
                ],
                "total_causes_analyzed": 12,
                "fmea_document_used": "fmea.xlsx",
                "execution_time_seconds": 4.2,
                "error": None
            }
        }
