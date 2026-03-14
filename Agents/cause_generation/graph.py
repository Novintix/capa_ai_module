"""
Cause Generation Agent Graph
LangGraph workflow definition
"""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    initialize_node,
    validate_fmea_node,
    parse_fmea_node,
    parse_question_node,
    match_fmea_node,
    extract_causes_node,
    process_with_llm_node,
    finalize_node
)


def create_cause_generation_graph():
    """
    Create the cause generation workflow graph
    
    Flow:
    1. initialize -> validate_fmea (always)
    2. validate_fmea -> parse_fmea OR process_with_llm (conditional: FMEA available)
    3. parse_fmea -> parse_question OR finalize (conditional: error handling)
    4. parse_question -> match_fmea (always)
    5. match_fmea -> extract_causes OR process_with_llm (conditional: no matches)
    6. extract_causes -> process_with_llm (always)
    7. process_with_llm -> finalize (always)
    8. finalize -> END (always)
    """
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("validate_fmea", validate_fmea_node)
    workflow.add_node("parse_fmea", parse_fmea_node)
    workflow.add_node("parse_question", parse_question_node)
    workflow.add_node("match_fmea", match_fmea_node)
    workflow.add_node("extract_causes", extract_causes_node)
    workflow.add_node("process_with_llm", process_with_llm_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("initialize")
    
    # Routing function for conditional edges
    def route_from_node(state: AgentState) -> str:
        """Route based on next_step in state"""
        next_step = state.get("next_step", "end")
        if next_step == "end":
            return END
        return next_step
    
    # Add edges
    # Simple edges (always same destination)
    workflow.add_edge("initialize", "validate_fmea")
    workflow.add_edge("parse_question", "match_fmea")
    workflow.add_edge("extract_causes", "process_with_llm")
    workflow.add_edge("process_with_llm", "finalize")
    
    # Conditional edges (can go to different destinations based on state)
    workflow.add_conditional_edges("validate_fmea", route_from_node)  # -> parse_fmea OR process_with_llm
    workflow.add_conditional_edges("parse_fmea", route_from_node)     # -> parse_question OR finalize
    workflow.add_conditional_edges("match_fmea", route_from_node)     # -> extract_causes OR process_with_llm
    workflow.add_conditional_edges("finalize", route_from_node)       # -> END
    
    # Compile graph
    return workflow.compile()
