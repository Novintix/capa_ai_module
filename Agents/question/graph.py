"""
LangGraph Workflow Definition
Defines the Why Question Agent graph structure and routing logic.
"""

from typing import Literal
from langgraph.graph import StateGraph

from .state import AgentState
from .nodes import (
    initialize_state_node,
    validate_inputs_node,
    generate_why_question_node,
    finalize_node
)


# ============================================================================
# ROUTING LOGIC
# ============================================================================

def route_after_validate(
    state: AgentState,
) -> Literal["generate_why_question", "finalize"]:
    """Router: After validation, proceed only if inputs are valid."""
    if state.get("validated") and not state.get("error"):
        return "generate_why_question"
    return "finalize"


def route_after_generate(state: AgentState) -> Literal["finalize"]:
    """Router: Always move to finalize after the generation step."""
    return "finalize"


def route_after_finalize(state: AgentState) -> Literal["__end__"]:
    """Router: Always end after finalize."""
    return "__end__"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_why_question_graph(checkpointer=None):
    """
    Create and compile the Why Question Agent graph.
    Orchestration is intentionally separate from node logic.

    Args:
        checkpointer: Optional LangGraph checkpointer (e.g. RedisSaver).
                      When provided, state is persisted between invocations
                      using the thread_id (complaint_id) in the config.

    Flow:
        initialize
            -> validate_inputs
                -> generate_why_question  (if inputs valid)
                -> finalize               (if inputs invalid)
            -> finalize
                -> __end__
    """
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("initialize", initialize_state_node)
    workflow.add_node("validate_inputs", validate_inputs_node)
    workflow.add_node("generate_why_question", generate_why_question_node)
    workflow.add_node("finalize", finalize_node)

    # Entry point
    workflow.set_entry_point("initialize")

    # Edges
    workflow.add_edge("initialize", "validate_inputs")
    workflow.add_conditional_edges("validate_inputs", route_after_validate)
    workflow.add_conditional_edges("generate_why_question", route_after_generate)
    workflow.add_conditional_edges("finalize", route_after_finalize)

    return workflow.compile(checkpointer=checkpointer)
