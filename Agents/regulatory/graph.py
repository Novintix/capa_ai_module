"""
LangGraph Workflow Definition
Defines the regulatory agent graph structure and routing logic.
"""

from typing import Literal
from langgraph.graph import StateGraph

from .state import AgentState
from .nodes import (
    initialize_state_node,
    normalize_input_node,
    evaluate_rules_node,
    select_rule_node,
    calculate_timeline_node,
    extract_decision_node,
    generate_justification_node,
    no_match_fallback_node,
    finalize_node
)


# ============================================================================
# ROUTING LOGIC
# ============================================================================

def route_after_normalize(state: AgentState) -> Literal["evaluate_rules", "no_match_fallback"]:
    """Router: Decide next step after normalization."""
    if state.get("error"):
        return "no_match_fallback"
    return "evaluate_rules"


def route_after_evaluate(state: AgentState) -> Literal["select_rule", "no_match_fallback"]:
    """Router: Decide next step after rule evaluation."""
    matched_rules = state.get("matched_rules")
    if matched_rules and len(matched_rules) > 0:
        return "select_rule"
    return "no_match_fallback"


def route_after_select(state: AgentState) -> Literal["calculate_timeline", "no_match_fallback"]:
    """Router: Decide next step after rule selection."""
    if state.get("selected_rule") and not state.get("error"):
        return "calculate_timeline"
    return "no_match_fallback"


def route_after_calculate(state: AgentState) -> Literal["extract_decision", "no_match_fallback"]:
    """Router: Decide next step after timeline calculation."""
    if state.get("due_date") and not state.get("error"):
        return "extract_decision"
    return "no_match_fallback"


def route_after_extract(state: AgentState) -> Literal["generate_justification", "no_match_fallback"]:
    """Router: Decide next step after decision extraction."""
    if state.get("matched_rule_id") and not state.get("error"):
        return "generate_justification"
    return "no_match_fallback"


def route_after_justification(state: AgentState) -> Literal["finalize"]:
    """Router: Always go to finalize after justification."""
    return "finalize"


def route_after_fallback(state: AgentState) -> Literal["finalize"]:
    """Router: Always go to finalize after fallback."""
    return "finalize"


def route_after_finalize(state: AgentState) -> Literal["__end__"]:
    """Router: Always end after finalize."""
    return "__end__"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_regulatory_graph() -> StateGraph:
    """
    Create the regulatory agent graph.
    Orchestration is separate from node logic.
    """
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_state_node)
    workflow.add_node("normalize_input", normalize_input_node)
    workflow.add_node("evaluate_rules", evaluate_rules_node)
    workflow.add_node("select_rule", select_rule_node)
    workflow.add_node("calculate_timeline", calculate_timeline_node)
    workflow.add_node("extract_decision", extract_decision_node)
    workflow.add_node("generate_justification", generate_justification_node)
    workflow.add_node("no_match_fallback", no_match_fallback_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("initialize")
    
    # Add edges
    workflow.add_edge("initialize", "normalize_input")
    workflow.add_conditional_edges("normalize_input", route_after_normalize)
    workflow.add_conditional_edges("evaluate_rules", route_after_evaluate)
    workflow.add_conditional_edges("select_rule", route_after_select)
    workflow.add_conditional_edges("calculate_timeline", route_after_calculate)
    workflow.add_conditional_edges("extract_decision", route_after_extract)
    workflow.add_conditional_edges("generate_justification", route_after_justification)
    workflow.add_conditional_edges("no_match_fallback", route_after_fallback)
    workflow.add_conditional_edges("finalize", route_after_finalize)
    
    return workflow.compile()
