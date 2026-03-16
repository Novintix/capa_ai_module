"""
model.py

Pydantic schemas for CAPA Effectiveness Evaluation Agent.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ActionItemInput(BaseModel):
    action_id: str = Field(..., description="Action ID")
    action_description: str = Field(..., description="Description of the action")

class EffectivenessEvaluationInput(BaseModel):
    root_cause_description: str = Field(..., description="Root Cause Description")
    actions: List[ActionItemInput] = Field(..., description="List of Corrective or Preventive Actions")
    system_context: str = Field(..., description="System Context (process, system, or operational environment where the issue occurred)")
    supporting_evidence: str = Field(..., description="Supporting Evidence (inspection reports, containment actions, validation records, monitoring results)")
    effectiveness_evaluation_criteria: Optional[str] = Field("Evaluate based on Root Cause Coverage (0-40), Recurrence Prevention Capability (0-30), Impact on System Reliability (0-20), Implementation Feasibility (0-10).", description="Effectiveness Evaluation Criteria")

class EvaluatedAction(BaseModel):
    action_id: str = Field(..., description="Action ID")
    action_description: str = Field(..., description="Action Description")
    root_cause_addressed: Literal["Yes", "Partially", "No"] = Field(..., description="Root Cause Addressed")
    recurrence_prevention_level: Literal["High", "Medium", "Low"] = Field(..., description="Recurrence Prevention Level")
    system_impact: Literal["High", "Medium", "Low"] = Field(..., description="System Impact")
    effectiveness_score: int = Field(..., ge=0, le=100, description="Effectiveness Score (0-100)")
    confidence_level: Literal["High", "Medium", "Low"] = Field(..., description="Confidence Level")
    explanation_of_evaluation: str = Field(..., description="Explanation of Evaluation")

class EffectivenessEvaluationRequest(BaseModel):
    """API request wrapper"""
    evaluation_input: EffectivenessEvaluationInput = Field(..., description="Inputs for effectiveness evaluation")

class EffectivenessEvaluationResponse(BaseModel):
    """API response with effectiveness evaluation"""
    evaluated_actions: List[EvaluatedAction] = Field(..., description="Ranked list of evaluated actions")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score (0-1)")
    notes: Optional[str] = Field(None, description="Additional notes")
