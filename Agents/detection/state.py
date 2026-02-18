"""
Agent State Definition
Structured state for Detection Agent using TypedDict.
"""

from typing import TypedDict, Optional, List, Dict


class AgentState(TypedDict):
    """
    Structured state for Detection Agent.
    Every field is explicitly defined.
    """
    # Input
    complaint_id: str
    complaint_source: str
    complaint_description: str
    policy_document_path: Optional[str]
    
    # Intermediate
    policy_text: Optional[str]
    policy_rules: Optional[List[Dict]]
    has_policy: bool
    
    # Output
    detection_score: Optional[int]
    confidence: Optional[float]
    rule_reference: Optional[str]
    explanation: Optional[str]
    decision_source: Optional[str]
    
    # Control
    iteration: int
    max_iterations: int
    error: Optional[str]
    next_step: Optional[str]
