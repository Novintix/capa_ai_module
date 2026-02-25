"""
graph.py

Defines LangGraph workflow for CAPA Action Plan Agent.

Flow:
  generate_actions_node → validate_actions_node → Output
"""

from langgraph.graph import StateGraph
from .state import ActionPlanState
from .nodes import generate_actions_node, validate_actions_node


def build_graph():
    """Build and compile CAPA action plan graph"""
    
    builder = StateGraph(ActionPlanState)

    # Add nodes
    builder.add_node("generate_actions", generate_actions_node)
    builder.add_node("validate_actions", validate_actions_node)

    # Define flow
    builder.set_entry_point("generate_actions")
    builder.add_edge("generate_actions", "validate_actions")
    builder.set_finish_point("validate_actions")

    return builder.compile()
