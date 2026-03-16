"""
Document Ingestion Agent State
TypedDict for LangGraph state management
"""

from typing import TypedDict, Dict, Any, Optional


class AgentState(TypedDict, total=False):
    """
    State for Document Ingestion Agent
    Uses total=False to allow dynamic fields
    """
    # Input fields
    document_id: str
    file_path: str
    extraction_mode: str
    include_metadata: bool
    use_llm_structuring: bool
    
    # Processing fields
    document_type: str
    file_extension: str
    file_metadata: Dict[str, Any]
    extracted_text: Optional[str]
    structured_data: Optional[Dict[str, Any]]
    ocr_data: Optional[Dict[str, Any]]
    llm_structured_data: Optional[Dict[str, Any]]
    
    # Output fields
    success: bool
    error_message: Optional[str]
    processing_time: float
    
    # Control fields
    iteration: int
    max_iterations: int
    next_step: str
    error: Optional[str]