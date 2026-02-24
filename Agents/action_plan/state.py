"""
state.py

Defines ActionPlanState for CAPA Action Plan LangGraph workflow.
"""

from typing import TypedDict, Optional, List, Dict, Any


class ActionPlanState(TypedDict, total=False):
    """State passed through action plan graph nodes"""
    
    # Input
    capa_input: Dict[str, Any]
    
    # Processing
    action_items: Optional[List[Dict[str, Any]]]
    total_actions: Optional[int]
    primary_actions: Optional[int]
    preventive_systemic_actions: Optional[int]
    confidence_score: Optional[float]
    notes: Optional[str]
    
    # Error tracking
    error: Optional[str]
