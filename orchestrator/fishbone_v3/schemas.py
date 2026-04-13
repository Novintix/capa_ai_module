"""
Fishbone v3 Orchestrator Schemas
Input/Output models for single-depth fishbone analysis with HITL (Human-in-the-Loop)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class DecisionAction(str, Enum):
    """Actions a human can take for a cause"""
    RCA = "RCA"
    PROCEED = "PROCEED"
    DISMISS = "DISMISS"


class FishboneV3Input(BaseModel):
    """Input schema for Fishbone v3 Orchestrator - HITL Analysis"""
    complaint_id: str = Field(
        ...,
        description="Unique identifier for the complaint record"
    )
    complaint: str = Field(
        ...,
        description="The problem statement or complaint description"
    )
    evidence: Optional[str] = Field(
        default="",
        description="Supporting facts, observations, measurements, or data"
    )
    sop: Optional[str] = Field(
        default="",
        description="Standard Operating Procedure relevant to the problem"
    )
    fmea_document_path: Optional[str] = Field(
        default=None,
        description="Path to FMEA Excel document for cause extraction"
    )
    evidence_files: Optional[List[str]] = Field(
        default=None,
        description="List of evidence file paths (PDF, DOCX, XLSX, images, logs)"
    )
    logs: Optional[str] = Field(default=None, description="System logs")
    reports: Optional[str] = Field(default=None, description="Investigation reports")
    process_data: Optional[str] = Field(default=None, description="Process data")
    historical_capa: Optional[str] = Field(default=None, description="Historical CAPA records")
    policies: Optional[str] = Field(default=None, description="Relevant policies")
    investigation_records: Optional[str] = Field(default=None, description="Investigation records")
    supporting_system_information: Optional[str] = Field(default=None, description="System information")

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "FISHBONE-V3-001",
                "complaint": "Tablet weight was incorrect during production",
                "evidence": "Weight measurements show 5% deviation",
            }
        }


class CauseDecision(BaseModel):
    """Human decision for a specific cause"""
    cause_id: str = Field(..., description="The ID of the cause")
    action: DecisionAction = Field(..., description="Action: RCA or PROCEED")
    comment: Optional[str] = Field(None, description="Optional human comment")


class FishboneV3DecisionInput(BaseModel):
    """Input for submitting human decisions"""
    complaint_id: str = Field(..., description="The complaint ID")
    decisions: List[CauseDecision] = Field(..., description="List of decisions for causes")


class CauseDetail(BaseModel):
    """Detailed information about a single cause with 6M categorization and human decision"""
    cause_id: str = Field(..., description="Unique identifier for the cause")
    cause_text: str = Field(..., description="Description of the cause")
    process_step: Optional[str] = Field(None, description="Process step where cause occurs")
    category: Optional[str] = Field(None, description="6M Category")
    category_confidence: Optional[float] = Field(None, description="Confidence (0.0-1.0)")
    category_reasoning: Optional[str] = Field(None, description="Reasoning for category")
    secondary_categories: Optional[List[str]] = Field(default_factory=list)
    failure_mode: Optional[str] = Field(None)
    potential_effects: Optional[str] = Field(None)
    severity: Optional[int] = Field(None)
    occurrence: Optional[int] = Field(None)
    detection: Optional[int] = Field(None)
    current_controls: Optional[str] = Field(None)
    source: Optional[str] = Field(None, description="Source (FMEA or LLM_Generated)")
    validation_status: Optional[str] = Field(None, description="matched, partially_matched, not_matched")
    validation_confidence: Optional[float] = Field(None)
    validation_rationale: Optional[str] = Field(None)
    
    # Zero Evidence Agent fields (when no high confidence causes)
    zero_evidence_rank: Optional[int] = Field(None, description="Rank from Zero Evidence Agent")
    zero_evidence_score: Optional[float] = Field(None, description="Score from Zero Evidence Agent")
    zero_evidence_reasoning: Optional[str] = Field(None, description="Reasoning from Zero Evidence Agent")
    
    # HITL Fields
    human_decision: Optional[DecisionAction] = Field(None, description="Decision made by human")
    human_comment: Optional[str] = Field(None, description="Comment from human")


class FishboneV3Output(BaseModel):
    """Output schema for Fishbone v3 - HITL Analysis"""
    complaint_id: str = Field(..., description="The complaint ID analyzed")
    status: str = Field(..., description="WAIT_FOR_HUMAN, COMPLETED, or ERROR")
    
    confidence: Optional[str] = Field(None, description="Overall confidence level")
    mode: str = Field(default="HITL_V3", description="Analysis mode")
    
    # Cause statistics
    total_causes_found: int = Field(..., description="Total number of causes identified")
    causes_validated_with_evidence: int = Field(default=0, description="Number of causes validated against evidence")
    high_confidence_causes_count: int = Field(default=0, description="Number of causes with validation confidence >= 0.9")
    low_confidence_causes_count: int = Field(default=0, description="Number of causes with validation confidence < 0.9")
    
    # Detailed breakdown by stage
    all_causes_found: List[CauseDetail] = Field(default_factory=list, description="Stage 1: All causes from ListCausesAgent")
    all_categorized_causes: List[CauseDetail] = Field(default_factory=list, description="Stage 2: All causes after 6M categorization")
    all_validated_causes: List[CauseDetail] = Field(default_factory=list, description="Stage 3: All causes after validation against evidence")
    high_confidence_causes: List[CauseDetail] = Field(default_factory=list, description="Stage 4a: High confidence causes (>= 0.9) for human review")
    low_confidence_causes: List[CauseDetail] = Field(default_factory=list, description="Stage 4b: Low confidence causes (< 0.9)")
    
    # Zero Evidence Agent output (only when executed)
    zero_evidence_result: Optional[Dict[str, Any]] = Field(None, description="Stage 5: Zero Evidence Agent ranking output (when no high confidence causes)")
    
    # Legacy fields for backward compatibility
    causes_found: int = Field(..., description="Number of causes shown (high confidence only for HITL)")
    causes: List[CauseDetail] = Field(default_factory=list, description="Causes shown for review (high confidence >= 0.9)")
    
    category_summary: Optional[Dict[str, int]] = Field(None)
    validated_causes_count: int = Field(default=0)
    
    execution_time_seconds: Optional[float] = Field(None)
    stopping_reason: Optional[str] = Field(None)
    error: Optional[str] = Field(None)
    execution_trace: Optional[List[str]] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "FISHBONE-V3-001",
                "status": "WAIT_FOR_HUMAN",
                "causes_found": 5,
                "causes": [
                    {
                        "cause_id": "C1",
                        "cause_text": "Machine calibration",
                        "category": "Machine",
                        "validation_status": "matched",
                        "source": "FMEA"
                    }
                ]
            }
        }
