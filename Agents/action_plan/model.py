"""
model.py

Pydantic schemas for CAPA Action Plan Agent.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CapaActionItem(BaseModel):
    """Single action plan row with 9 columns"""
    action_type: str = Field(..., description="Correction/Corrective/Preventive/Systemic")
    action_description: str = Field(..., description="Specific, measurable description")
    assigned_to: str = Field(..., description="Department (not individual name)")
    planned_due_date: str = Field(..., description="YYYY-MM-DD format")
    resources_required: str = Field(..., description="Tools, personnel, equipment needed")
    verification_plan: str = Field(..., description="Measurable validation method")
    training_requirements: str = Field(..., description="Yes/No + Training ID or N/A")
    document_updates_required: str = Field(..., description="Document IDs (SOP-XXX, WI-XXX) or N/A")
    change_control_reference: str = Field(..., description="CC-###, EC-###, SC-### or N/A")


class CapaInput(BaseModel):
    """Input structure for CAPA action plan generation"""
    investigation_summary: str = Field(..., description="Summary of investigation")
    containment_actions: str = Field(..., description="Actions taken to contain the issue")
    five_why_analysis: str = Field(..., description="5 Why analysis results")
    primary_root_cause: str = Field(..., description="Primary root cause identified")
    contributing_root_causes: Optional[List[str]] = Field(None, description="Contributing root causes")
    systemic_root_causes: Optional[List[str]] = Field(None, description="Systemic root causes")
    evidence_collected: str = Field(..., description="Evidence supporting root cause")
    root_cause_verification_status: str = Field(..., description="Verified/Pending/Not Required")
    severity_level: Optional[str] = Field(None, description="Critical/Major/Minor")
    timeline_constraint: Optional[str] = Field(None, description="e.g., 30 days, 90 days")
    available_resources: Optional[str] = Field(None, description="Budget, personnel, equipment available")


class CapaActionPlanRequest(BaseModel):
    """API request wrapper"""
    capa_input: CapaInput = Field(..., description="CAPA investigation and root cause data")


class CapaActionPlanResponse(BaseModel):
    """API response with action plan"""
    action_items: List[CapaActionItem] = Field(..., description="9-column action plan")
    total_actions: int = Field(..., description="Total number of actions")
    primary_actions: int = Field(..., description="Actions for primary root cause")
    preventive_systemic_actions: int = Field(..., description="Preventive and systemic actions")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in plan (0-1)")
    notes: Optional[str] = Field(None, description="Additional audit notes")
