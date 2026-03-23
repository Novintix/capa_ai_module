"""
Cause Generation Agent State
TypedDict for LangGraph state management
"""

from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict, total=False):
    """
    State for Cause Generation Agent
    Uses total=False to allow dynamic fields
    """
    # Input fields
    question_id: str
    question: str
    context: Optional[str]
    fmea_document_path: str
    evidence_context: Optional[Dict[str, Any]]  # Evidence for cause extraction
    
    # Processing fields
    fmea_data: List[Dict[str, Any]]  # Parsed FMEA rows
    matched_rows: List[Dict[str, Any]]  # Matched FMEA rows
    extracted_causes: List[Dict[str, Any]]  # Extracted causes
    evidence_extracted_causes: List[Dict[str, Any]]  # Causes extracted from evidence
    fmea_available: bool  # Whether FMEA document is available
    question_keywords: List[str]  # Keywords extracted from question
    
    # Output fields
    causes: List[Dict[str, Any]]  # Final list of causes
    total_causes: int
    matched_entries: int
    evidence_extracted: int  # Number of causes extracted from evidence
    confidence: float
    notes: Optional[str]
    fmea_document_used: Optional[str]
    
    # Control fields
    iteration: int
    max_iterations: int
    next_step: str
    error: Optional[str]
