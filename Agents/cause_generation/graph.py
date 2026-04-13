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
    extract_from_evidence_node,
    match_fmea_node,
    extract_causes_node,
    process_with_llm_node,
    deduplicate_causes_node,
    score_causes_node,
    finalize_node
)


def create_cause_generation_graph():
    """
    Create the cause generation workflow graph
    
    Flow:
    1. initialize -> validate_fmea (always)
    2. validate_fmea -> parse_fmea OR process_with_llm (conditional: FMEA available)
    3. parse_fmea -> parse_question OR finalize (conditional: error handling)
    4. parse_question -> extract_from_evidence (always)
    5. extract_from_evidence -> match_fmea (always)
    6. match_fmea -> extract_causes OR process_with_llm (conditional: no matches)
    7. extract_causes -> process_with_llm (always)
    8. process_with_llm -> deduplicate_causes (always)
    9. deduplicate_causes -> score_causes (always)
    10. score_causes -> finalize (always)
    11. finalize -> END (always)
    """
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("validate_fmea", validate_fmea_node)
    workflow.add_node("parse_fmea", parse_fmea_node)
    workflow.add_node("parse_question", parse_question_node)
    workflow.add_node("extract_from_evidence", extract_from_evidence_node)
    workflow.add_node("match_fmea", match_fmea_node)
    workflow.add_node("extract_causes", extract_causes_node)
    workflow.add_node("process_with_llm", process_with_llm_node)
    workflow.add_node("deduplicate_causes", deduplicate_causes_node)
    workflow.add_node("score_causes", score_causes_node)
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
    workflow.add_edge("extract_causes", "process_with_llm")
    workflow.add_edge("deduplicate_causes", "score_causes")
    workflow.add_edge("score_causes", "finalize")
    
    # Conditional edges (can go to different destinations based on state)
    workflow.add_conditional_edges("validate_fmea", route_from_node)        # -> parse_fmea OR process_with_llm
    workflow.add_conditional_edges("parse_fmea", route_from_node)           # -> parse_question OR finalize
    workflow.add_conditional_edges("parse_question", route_from_node)       # -> extract_from_evidence
    workflow.add_conditional_edges("extract_from_evidence", route_from_node) # -> match_fmea
    workflow.add_conditional_edges("match_fmea", route_from_node)           # -> extract_causes OR process_with_llm
    workflow.add_conditional_edges("process_with_llm", route_from_node)     # -> deduplicate_causes OR finalize
    workflow.add_conditional_edges("finalize", route_from_node)             # -> END
    
    # Compile graph
    return workflow.compile()
