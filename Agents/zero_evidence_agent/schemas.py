"""
Data Schemas
Defines the structure of input and output data for Zero Evidence Agent.
"""

from pydantic import BaseModel, Field
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


class ZeroEvidenceInput(BaseModel):
    """Input to Zero Evidence Agent from Cause Generation Agent"""

    question_id: str = Field(..., description="Question identifier")
    question: str = Field(..., description="Original why question")
    causes: List[CauseInput] = Field(..., description="List of candidate causes to evaluate")
    total_causes: int = Field(..., description="Total number of causes provided")

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

    mode: str = Field(default="ZERO_EVIDENCE_MODE", description="Agent mode identifier")
    selected_root_cause: SelectedRootCause = Field(..., description="The single most critical root cause")
    confidence: str = Field(default="MEDIUM", description="Confidence level of the selection")

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "ZERO_EVIDENCE_MODE",
                "selected_root_cause": {
                    "cause_id": "C002",
                    "cause_text": "Ink adhesion failure, incorrect curing, wrong artwork version",
                    "process_step": "Syringe Marking (Graduation & Text)",
                    "reason": "Highest severity with patient safety impact and single point failure potential"
                },
                "confidence": "MEDIUM"
            }
        }
