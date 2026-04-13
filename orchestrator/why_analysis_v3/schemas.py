"""
Pydantic schemas for Why Analysis V3 orchestrator.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WhyAnalysisV3Input(BaseModel):
    """Input schema for Why Analysis V3."""
    
    complaint_id: str = Field(..., description="Unique identifier for the complaint")
    complaint: str = Field(..., description="Description of the complaint or issue")
    evidence: str = Field(default="", description="Investigation evidence text")
    sop: str = Field(default="", description="Standard Operating Procedure text")
    fmea_document_path: Optional[str] = Field(default=None, description="Path to FMEA document")
    session_id: Optional[str] = Field(default=None, description="Session ID for resuming")
    
    # Optional evidence fields
    evidence_files: Optional[List[str]] = Field(default=None, description="List of evidence file paths")
    logs: Optional[Any] = Field(default=None, description="System logs")
    reports: Optional[Any] = Field(default=None, description="Investigation reports")
    process_data: Optional[Any] = Field(default=None, description="Process data")
    historical_capa: Optional[Any] = Field(default=None, description="Historical CAPA records")
    policies: Optional[Any] = Field(default=None, description="Relevant policies")
    investigation_records: Optional[Any] = Field(default=None, description="Investigation records")
    supporting_system_information: Optional[Any] = Field(default=None, description="Supporting system info")


class HumanReviewInput(BaseModel):
    """Input schema for human review response."""
    
    session_id: str = Field(..., description="Session ID to resume")
    selected_cause_id: str = Field(..., description="ID of the cause selected by human reviewer")
    decision: str = Field(default="root_cause", description="Human decision: 'root_cause' (end analysis) or 'continue' (dig deeper)")
    
    class Config:
        use_enum_values = True


class WhyChainEntry(BaseModel):
    """One entry in the Why chain."""
    
    loop: int
    question: str
    selected_cause: str
    selected_cause_id: str
    confidence: float
    human_approved: bool


class WhyAnalysisV3Output(BaseModel):
    """Output schema for Why Analysis V3."""
    
    complaint_id: str
    session_id: Optional[str]
    status: str
    mode: str
    analysis_depth: int
    ai_flagged: bool
    manual_investigation_required: bool
    stopping_reason: Optional[str]
    
    # Human review
    awaiting_human_review: bool = False
    human_review_message: Optional[str] = None
    validated_causes: Optional[List[Dict[str, Any]]] = None
    
    # Results
    root_cause: Optional[Dict[str, Any]] = None
    why_chain: List[Dict[str, Any]] = []
    iteration_outputs: List[Dict[str, Any]] = []
    
    # Summary
    validation_summary: Dict[str, Any] = {}
    execution_time_seconds: float = 0.0
    error: Optional[str] = None
    node_log: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
