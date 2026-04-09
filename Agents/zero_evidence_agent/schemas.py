"""
Data Schemas
Defines the structure of input and output data for Zero Evidence Agent.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict


class CauseInput(BaseModel):
    """Single cause entry from cause generation agent"""

    cause_id: str = Field(..., description="Unique cause identifier")
    cause_text: str = Field(..., description="Cause description")
    process_step: str = Field(..., description="Associated process step")
    failure_mode: str = Field(..., description="Associated failure mode")
    potential_effects: Optional[str] = Field(None, description="Potential effects on the system or patient")
    severity: Optional[int] = Field(None, description="Severity rating from FMEA (1-10)")
    occurrence: Optional[int] = Field(None, description="Occurrence rating from FMEA (1-10)")
    detection: Optional[int] = Field(None, description="Detection rating from FMEA (1-10)")
    current_controls: Optional[str] = Field(None, description="Current process controls in place")
    source: str = Field(default="FMEA", description="Source of cause")
    
    @field_validator('cause_id', 'cause_text', 'process_step', 'failure_mode')
    @classmethod
    def validate_required_strings(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return str(v).strip()
    
    @field_validator('severity', 'occurrence', 'detection')
    @classmethod
    def validate_scores(cls, v, info):
        if v is not None:
            if not isinstance(v, int):
                raise ValueError(f"{info.field_name} must be an integer")
            if v < 1 or v > 10:
                raise ValueError(f"{info.field_name} must be between 1 and 10")
        return v


class ZeroEvidenceInput(BaseModel):
    """Input to Zero Evidence Agent from Cause Generation Agent"""

    question_id: str = Field(..., description="Question identifier")
    question: str = Field(..., description="Original why question")
    causes: List[CauseInput] = Field(..., description="List of candidate causes to evaluate")
    total_causes: int = Field(..., description="Total number of causes provided")
    
    @field_validator('question_id')
    @classmethod
    def validate_question_id(cls, v):
        if not v or not v.strip():
            raise ValueError("question_id cannot be empty")
        return v.strip()
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError("question cannot be empty")
        if len(v.strip()) < 5:
            raise ValueError("question must be at least 5 characters long")
        return v.strip()
    
    @field_validator('causes')
    @classmethod
    def validate_causes(cls, v):
        if not v or len(v) == 0:
            raise ValueError("causes list cannot be empty")
        return v
    
    @field_validator('total_causes')
    @classmethod
    def validate_total_causes(cls, v, info):
        if v < 1:
            raise ValueError("total_causes must be at least 1")
        # Check consistency with causes list length
        causes = info.data.get('causes', [])
        if causes and len(causes) != v:
            raise ValueError(f"total_causes ({v}) does not match causes list length ({len(causes)})")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "question_id": "Q001",
                "question": "Why was the syringe marking incorrect?",
                "causes": [
                    {
                        "cause_id": "C001",
                        "cause_text": "Excess ink, insufficient drying time",
                        "process_step": "Syringe Marking (Graduation & Text)",
                        "failure_mode": "Smudged or blurred markings",
                        "potential_effects": "Poor readability leading to dosing error",
                        "severity": 7,
                        "occurrence": 4,
                        "detection": 5,
                        "current_controls": "Optimize ink viscosity and curing parameters",
                        "source": "FMEA"
                    }
                ],
                "total_causes": 1
            }
        }


class SelectedRootCause(BaseModel):
    """The single selected root cause output"""

    cause_id: str = Field(..., description="Identifier of the selected cause")
    cause_text: str = Field(..., description="Text of the selected cause")
    process_step: str = Field(..., description="Process step of the selected cause")
    reason: str = Field(..., description="Reasoning for why this cause was selected")


class ZeroEvidenceResult(BaseModel):
    """Output of Zero Evidence Agent — single Most Critical Functional Cause"""

    selected_root_cause: SelectedRootCause = Field(..., description="The single most critical root cause")
    confidence: float = Field(..., description="Numerical confidence score (0.0-1.0) based on scoring quality and separation")

    class Config:
        json_schema_extra = {
            "example": {
                "selected_root_cause": {
                    "cause_id": "C002",
                    "cause_text": "Ink adhesion failure, incorrect curing, wrong artwork version",
                    "process_step": "Syringe Marking (Graduation & Text)",
                    "reason": "Highest severity with patient safety impact and single point failure potential"
                },
                "confidence": 0.82
            }
        }
