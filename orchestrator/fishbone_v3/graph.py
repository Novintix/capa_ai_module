"""
LangGraph Workflow Definition — Fishbone V3 Orchestrator
Defines the graph structure and routing logic for HITL (Human-in-the-Loop) analysis.

Graph flow:
  initialize
    → list_causes
      → categorize_causes
        → validate_causes
          → filter_high_confidence
            → wait_for_human (if high confidence causes exist)
            → complete_analysis (if no high confidence causes)
          → wait_for_human
            → record_decisions
              → complete_analysis
          → complete_analysis
            → END
"""
from langgraph.graph import StateGraph, END
from .state import FishboneV3State
from .nodes import (
    initialize_node,
    list_causes_node,
    categorize_causes_node,
    validate_causes_node,
    filter_high_confidence_node,
    wait_for_human_node,
    record_decisions_node,
    complete_analysis_node,
)


# ============================================================================
# ROUTING LOGIC
# ============================================================================
def route_from_node(state: FishboneV3State) -> str:
    """
    Universal router: returns next_step from state.
    All nodes set state['next_step'] to control the flow.
    """
    next_step = state.get("next_step", END)
    if next_step == "end" or next_step is None:
        return END
    return next_step


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================
def create_fishbone_v3_graph():
    """
    Create and compile the Fishbone V3 Orchestrator graph.
    
    The graph orchestrates 3 main agents:
      1. Cause Generation Agent → finds/generates causes from FMEA or LLM
      2. Categorization Agent   → categorizes causes into 6M categories
      3. Validation Agent       → validates causes against evidence
    
    HITL Flow:
      - Filters causes with validation_confidence >= 0.9
      - Pauses for human review if high confidence causes exist
      - Human can choose RCA or PROCEED for each cause
      - Completes automatically if no high confidence causes
    """
    workflow = StateGraph(FishboneV3State)
    
    # Register nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("list_causes", list_causes_node)
    workflow.add_node("categorize_causes", categorize_causes_node)
    workflow.add_node("validate_causes", validate_causes_node)
    workflow.add_node("filter_high_confidence", filter_high_confidence_node)
    workflow.add_node("wait_for_human", wait_for_human_node)
    workflow.add_node("record_decisions", record_decisions_node)
    workflow.add_node("complete_analysis", complete_analysis_node)
    
    # Entry point
    workflow.set_entry_point("initialize")
    
    # Fixed edges
    workflow.add_edge("initialize", "list_causes")
    workflow.add_edge("list_causes", "categorize_causes")
    workflow.add_edge("categorize_causes", "validate_causes")
    workflow.add_edge("validate_causes", "filter_high_confidence")
    
    # Conditional edges — driven by state["next_step"]
    workflow.add_conditional_edges("filter_high_confidence", route_from_node)
    # → wait_for_human (if high confidence causes exist)
    # → complete_analysis (if no high confidence causes)
    
    workflow.add_conditional_edges("wait_for_human", route_from_node)
    # → record_decisions (when human submits decisions)
    
    workflow.add_edge("record_decisions", "complete_analysis")
    
    workflow.add_conditional_edges("complete_analysis", route_from_node)
    # → END (always)
    
    return workflow.compile()
