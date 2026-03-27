"""
Fishbone v2 Orchestrator Schemas
Input/Output models for single-depth fishbone analysis
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class FishboneInput(BaseModel):
    """Input schema for Fishbone v2 Orchestrator - Single Depth Analysis"""
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
                "complaint_id": "FISHBONE-2026-001",
                "complaint": "Tablet weight was incorrect during production batch #1234",
                "evidence": "Weight measurements show 5% deviation from specification",
                "fmea_document_path": "fmea.xlsx"
            }
        }


class CauseDetail(BaseModel):
    """Detailed information about a single cause with 6M categorization"""
    cause_id: str = Field(..., description="Unique identifier for the cause")
    cause_text: str = Field(..., description="Description of the cause")
    process_step: str = Field(..., description="Process step where cause occurs")
    category: Optional[str] = Field(None, description="6M Category: Man, Machine, Method, Material, Measurement, Environment")
    category_confidence: Optional[float] = Field(None, description="Confidence in category assignment (0.0-1.0)")
    category_reasoning: Optional[str] = Field(None, description="Reasoning for category assignment")
    secondary_categories: Optional[List[str]] = Field(default_factory=list, description="Secondary applicable categories")
    failure_mode: Optional[str] = Field(None, description="Type of failure")
    potential_effects: Optional[str] = Field(None, description="Potential impact")
    severity: Optional[int] = Field(None, description="Severity score (1-10)")
    occurrence: Optional[int] = Field(None, description="Occurrence score (1-10)")
    detection: Optional[int] = Field(None, description="Detection score (1-10)")
    current_controls: Optional[str] = Field(None, description="Current control measures")
    source: str = Field(..., description="Source of cause (FMEA or LLM_Generated)")
    validation_status: Optional[str] = Field(None, description="matched, partially_matched, not_matched")
    validation_confidence: Optional[float] = Field(None, description="Validation confidence (0.0-1.0)")


class RootCauseDetail(BaseModel):
    """Final selected root cause with complete context"""
    cause_id: str = Field(..., description="Identifier of the root cause")
    cause_text: str = Field(..., description="Description of the root cause")
    process_step: str = Field(..., description="Process step of the root cause")
    category: Optional[str] = Field(None, description="6M Category")
    category_confidence: Optional[float] = Field(None, description="Category confidence")
    failure_mode: Optional[str] = Field(None, description="Type of failure")
    potential_effects: Optional[str] = Field(None, description="Potential impact")
    severity: Optional[int] = Field(None, description="Severity score")
    occurrence: Optional[int] = Field(None, description="Occurrence score")
    detection: Optional[int] = Field(None, description="Detection score")
    current_controls: Optional[str] = Field(None, description="Current control measures")
    source: str = Field(..., description="Source (FMEA or LLM_Generated)")
    reason: str = Field(..., description="Reasoning for selection as root cause")
    confidence_score: Optional[float] = Field(None, description="Confidence in selection (0.0-1.0)")


class FishboneOutput(BaseModel):
    """Output schema for Fishbone v2 - Single Depth Analysis"""
    complaint_id: str = Field(..., description="The complaint ID analyzed")
    
    root_cause: Optional[RootCauseDetail] = Field(
        None,
        description="The final selected root cause"
    )
    
    confidence: str = Field(
        ...,
        description="Overall confidence level: LOW, MEDIUM, or HIGH"
    )
    
    mode: str = Field(
        ...,
        description="Analysis mode: SINGLE_SHOT"
    )
    
    causes_found: int = Field(
        ...,
        description="Total number of causes found"
    )
    
    causes: List[CauseDetail] = Field(
        default_factory=list,
        description="All causes with 6M categorization"
    )
    
    category_summary: Optional[Dict[str, int]] = Field(
        None,
        description="Count of causes per 6M category"
    )
    
    validated_causes_count: int = Field(
        default=0,
        description="Number of causes that passed validation"
    )
    
    high_confidence_causes_count: int = Field(
        default=0,
        description="Number of high confidence validated causes"
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
        description="Reason why the analysis stopped"
    )
    
    error: Optional[str] = Field(
        None,
        description="Error message if analysis failed"
    )
    
    execution_trace: Optional[List[str]] = Field(
        default_factory=list,
        description="Trace of agents executed in order"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "FISHBONE-2026-001",
                "root_cause": {
                    "cause_id": "C002",
                    "cause_text": "Compression force set incorrectly",
                    "process_step": "Tablet Compression",
                    "category": "Method",
                    "category_confidence": 0.92,
                    "severity": 8,
                    "source": "FMEA",
                    "reason": "Highest criticality score with high validation confidence"
                },
                "confidence": "HIGH",
                "mode": "SINGLE_SHOT",
                "causes_found": 10,
                "category_summary": {
                    "Man": 2,
                    "Machine": 3,
                    "Method": 3,
                    "Material": 1,
                    "Measurement": 1
                },
                "validated_causes_count": 8,
                "high_confidence_causes_count": 5,
                "execution_time_seconds": 8.5
            }
        }


    execution_trace: Optional[List[str]] = Field(
        default_factory=list,
        description="Trace of agents executed in order"
    )
