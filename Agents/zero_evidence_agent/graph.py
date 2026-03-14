"""
LangGraph Workflow Definition — Zero Evidence Agent
Defines the graph structure and routing logic.
"""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    initialize_node,
    validate_input_node,
    llm_evaluate_node,
    score_causes_node,
    select_cause_node,
    finalize_node,
)


# ============================================================================
# ROUTING LOGIC
# ============================================================================

def route_from_node(state: AgentState) -> str:
    """
    Universal router: returns next_step from state.
    All nodes set state['next_step'] to control the flow.
    """
    next_step = state.get("next_step", END)
    return next_step


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_zero_evidence_graph() -> StateGraph:
    """
    Create the Zero Evidence Agent graph.

    Flow:
      initialize --> validate_input
      validate_input --> llm_evaluate  (has causes)
                     --> END           (empty causes → error)
      llm_evaluate   --> score_causes  (always, even on LLM failure)
      score_causes   --> select_cause  (success)
                     --> finalize      (scoring error)
      select_cause   --> finalize      (always)
      finalize       --> END           (always)
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("validate_input", validate_input_node)
    workflow.add_node("llm_evaluate", llm_evaluate_node)
    workflow.add_node("score_causes", score_causes_node)
    workflow.add_node("select_cause", select_cause_node)
    workflow.add_node("finalize", finalize_node)

    # Set entry point
    workflow.set_entry_point("initialize")

    # Fixed edge: initialize always goes to validate_input
    workflow.add_edge("initialize", "validate_input")

    # Conditional edges driven by state["next_step"]
    workflow.add_conditional_edges("validate_input", route_from_node)   # -> llm_evaluate or END
    workflow.add_conditional_edges("llm_evaluate", route_from_node)     # -> score_causes
    workflow.add_conditional_edges("score_causes", route_from_node)     # -> select_cause or finalize
    workflow.add_conditional_edges("select_cause", route_from_node)     # -> finalize
    workflow.add_conditional_edges("finalize", route_from_node)         # -> END

    return workflow.compile()
