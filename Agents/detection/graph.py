"""
LangGraph Workflow Definition
Defines the detection agent graph structure and routing logic.
"""

from typing import Literal
from langgraph.graph import StateGraph

from .state import AgentState
from .nodes import (
    initialize_state_node,
    check_policy_node,
    extract_policy_node,
    parse_policy_node,
    score_with_policy_node,
    score_with_defaults_node,
    finalize_node
)


# ============================================================================
# ROUTING LOGIC
# ============================================================================

def route_after_check(state: AgentState) -> Literal["extract_policy", "score_with_defaults"]:
    """Router: Decide next step after policy check."""
    if state.get("has_policy") and not state.get("error"):
        return "extract_policy"
    return "score_with_defaults"


def route_after_extract(state: AgentState) -> Literal["parse_policy", "score_with_defaults"]:
    """Router: Decide next step after extraction."""
    if state.get("policy_text") and not state.get("error"):
        return "parse_policy"
    return "score_with_defaults"


def route_after_parse(state: AgentState) -> Literal["score_with_policy", "score_with_defaults"]:
    """Router: Decide next step after parsing."""
    if state.get("policy_rules") and not state.get("error"):
        return "score_with_policy"
    return "score_with_defaults"


def route_after_score(state: AgentState) -> Literal["finalize"]:
    """Router: Always go to finalize after scoring."""
    return "finalize"


def route_after_finalize(state: AgentState) -> Literal["__end__"]:
    """Router: Always end after finalize."""
    return "__end__"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_detection_graph() -> StateGraph:
    """
    Create the detection agent graph.
    Orchestration is separate from node logic.
    """
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_state_node)
    workflow.add_node("check_policy", check_policy_node)
    workflow.add_node("extract_policy", extract_policy_node)
    workflow.add_node("parse_policy", parse_policy_node)
    workflow.add_node("score_with_policy", score_with_policy_node)
    workflow.add_node("score_with_defaults", score_with_defaults_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("initialize")
    
    # Add edges
    workflow.add_edge("initialize", "check_policy")
    workflow.add_conditional_edges("check_policy", route_after_check)
    workflow.add_conditional_edges("extract_policy", route_after_extract)
    workflow.add_conditional_edges("parse_policy", route_after_parse)
    workflow.add_conditional_edges("score_with_policy", route_after_score)
    workflow.add_conditional_edges("score_with_defaults", route_after_score)
    workflow.add_conditional_edges("finalize", route_after_finalize)
    
    return workflow.compile()
