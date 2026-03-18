"""
graph.py

Defines LangGraph workflow for CAPA Effectiveness Evaluation Agent.
"""

from langgraph.graph import StateGraph
from .state import EffectivenessState
from .nodes import evaluate_actions_node, validate_evaluations_node

def build_graph():
    """Build and compile CAPA effectiveness evaluation graph"""
    
    builder = StateGraph(EffectivenessState)

    # Add node
    builder.add_node("evaluate_actions", evaluate_actions_node)
    builder.add_node("validate_evaluations", validate_evaluations_node)

    # Define flow
    builder.set_entry_point("evaluate_actions")
    builder.add_edge("evaluate_actions", "validate_evaluations")
    builder.set_finish_point("validate_evaluations")

    return builder.compile()
