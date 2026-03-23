"""
LangGraph Workflow Definition — Why Analysis Orchestrator
Defines the graph structure and routing logic.
Graph flow:
  initialize
    → generate_question
      → generate_causes
        → rank_causes (if causes found)
        → finalize    (if 0 causes)
      → rank_causes
        → check_iteration
          → generate_question  (FMEA mode: iterate)
          → finalize           (stop condition met)
      → check_iteration
        → finalize
    → finalize
      → END
"""
from langgraph.graph import StateGraph, END
from .state import OrchestratorState
from .nodes import (
    initialize_node,
    generate_question_node,
    generate_causes_node,
    rank_causes_node,
    check_iteration_node,
    finalize_node,
)
# ============================================================================
# ROUTING LOGIC
# ============================================================================
def route_from_node(state: OrchestratorState) -> str:
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
def create_why_analysis_graph():
    """
    Create and compile the Why Analysis Orchestrator graph.
    The graph orchestrates 3 sub-agents:
      1. Question Agent       → generates the next Why question
      2. Cause Generation Agent → finds/generates causes from FMEA or LLM
      3. Zero Evidence Agent   → ranks causes and selects the most critical
    Two modes:
      - FMEA_ITERATIVE     : Loops generate_question → generate_causes → rank_causes
                              until FMEA causes are exhausted or max depth reached
      - NO_FMEA_SINGLE_SHOT : One pass through the pipeline, then stops
    """
    workflow = StateGraph(OrchestratorState)
    # Register nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("generate_question", generate_question_node)
    workflow.add_node("generate_causes", generate_causes_node)
    workflow.add_node("rank_causes", rank_causes_node)
    workflow.add_node("check_iteration", check_iteration_node)
    workflow.add_node("finalize", finalize_node)
    # Entry point
    workflow.set_entry_point("initialize")
    # Fixed edge: initialize always goes to generate_question
    workflow.add_edge("initialize", "generate_question")
    # Conditional edges — all driven by state["next_step"]
    workflow.add_conditional_edges("generate_question", route_from_node)
    # → generate_causes (success)
    # → finalize (error)
    workflow.add_conditional_edges("generate_causes", route_from_node)
    # → rank_causes (causes found)
    # → finalize (no causes / error)
    workflow.add_conditional_edges("rank_causes", route_from_node)
    # → check_iteration (success)
    # → finalize (error)
    workflow.add_conditional_edges("check_iteration", route_from_node)
    # → generate_question (FMEA mode: continue iterating)
    # → finalize (stop condition met)
    workflow.add_conditional_edges("finalize", route_from_node)
    # → END (always)
    return workflow.compile()
