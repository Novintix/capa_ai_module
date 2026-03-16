"""
state.py

Defines EffectivenessState for CAPA Effectiveness Evaluation LangGraph workflow.
"""

from typing import TypedDict, Optional, List, Dict, Any

class EffectivenessState(TypedDict, total=False):
    """State passed through effectiveness graph nodes"""
    
    # Input
    evaluation_input: Dict[str, Any]
    
    # Processing
    evaluated_actions: Optional[List[Dict[str, Any]]]
    confidence_score: Optional[float]
    notes: Optional[str]
    
    # Error tracking
    error: Optional[str]
