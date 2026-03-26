from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import (
    initialize_state_node,
    fetch_historical_data_node,
    analyze_trend_node,
    finalize_node
)


def create_pattern_graph():
    """Create the LangGraph for the Pattern Agent."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("initialize", initialize_state_node)
    workflow.add_node("fetch_data", fetch_historical_data_node)
    workflow.add_node("analyze_trend", analyze_trend_node)
    workflow.add_node("finalize", finalize_node)

    # Set entry point
    workflow.set_entry_point("initialize")

    # Add edges
    workflow.add_edge("initialize", "fetch_data")
    workflow.add_edge("fetch_data", "analyze_trend")
    workflow.add_edge("analyze_trend", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile(name="A2_pattern_agent")