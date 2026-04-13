"""
Fishbone V3 State Definition
TypedDict for LangGraph state management
"""
from typing import TypedDict, List, Dict, Any, Optional


class FishboneV3State(TypedDict, total=False):
    """
    State for Fishbone V3 Orchestrator Graph
    
    Fields:
    - complaint_id: Unique identifier for the complaint
    - complaint: Problem statement
    - evidence: Supporting evidence
    - fmea_document_path: Path to FMEA document
    - causes: List of all causes found
    - categorized_causes: Causes with 6M categorization
    - validated_causes: Causes validated against evidence
    - high_confidence_causes: Causes with validation_confidence >= 0.9
    - category_summary: Count per category
    - validation_confidence: Overall validation confidence
    - human_decisions: Decisions from human (RCA/PROCEED)
    - next_step: Next node to execute
    - error: Error message if any
    - execution_trace: List of executed steps
    """
    # Input fields
    complaint_id: str
    complaint: str
    evidence: Optional[str]
    sop: Optional[str]
    fmea_document_path: Optional[str]
    evidence_files: Optional[List[str]]
    logs: Optional[str]
    reports: Optional[str]
    process_data: Optional[str]
    historical_capa: Optional[str]
    policies: Optional[str]
    investigation_records: Optional[str]
    supporting_system_information: Optional[str]
    
    # Processing fields
    causes: List[Dict[str, Any]]
    categorized_causes: List[Dict[str, Any]]
    validated_causes: List[Dict[str, Any]]
    high_confidence_causes: List[Dict[str, Any]]
    category_summary: Dict[str, int]
    validation_confidence: float
    
    # HITL fields
    human_decisions: Optional[List[Dict[str, Any]]]
    
    # Control fields
    next_step: str
    error: Optional[str]
    execution_trace: List[str]
    status: str
