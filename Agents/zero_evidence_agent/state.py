"""
Agent State Definition
Structured state for Zero Evidence Agent using TypedDict.
"""

from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict):
    """
    Structured state for Zero Evidence Agent.

    Every field is explicitly defined.
    This agent selects the Most Critical Functional Cause when
    no validation evidence or historical data exists.
    """
    # Input
    question_id: str
    question: str
    causes: List[Dict[str, Any]]
    total_causes: int

    # Intermediate
    llm_evaluations: Optional[List[Dict[str, Any]]]   # LLM reasoning per cause
    scored_causes: Optional[List[Dict[str, Any]]]     # Causes with computed scores

    # Output
    selected_cause_id: Optional[str]
    selected_cause_text: Optional[str]
    selected_cause_process_step: Optional[str]
    selection_reason: Optional[str]
    confidence_level: Optional[str]   # "MEDIUM" as per spec

    # Control
    iteration: int
    max_iterations: int
    error: Optional[str]
    next_step: Optional[str]
