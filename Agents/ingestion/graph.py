"""
Document Ingestion Agent Graph
LangGraph workflow definition
"""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    initialize_node,
    detect_type_node,
    extract_content_node,
    process_images_node,
    structure_with_llm_node,
    finalize_node
)


def create_ingestion_graph():
    """
    Create the document ingestion workflow graph
    
    Flow:
    1. initialize -> detect_type (always)
    2. detect_type -> extract_content OR finalize (conditional: file validation)
    3. extract_content -> process_images (always)
    4. process_images -> structure_with_llm OR finalize (conditional: LLM enabled)
    5. structure_with_llm -> finalize (always)
    6. finalize -> END (always)
    """
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("detect_type", detect_type_node)
    workflow.add_node("extract_content", extract_content_node)
    workflow.add_node("process_images", process_images_node)
    workflow.add_node("structure_with_llm", structure_with_llm_node)
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
    workflow.add_edge("initialize", "detect_type")
    workflow.add_edge("extract_content", "process_images")
    workflow.add_edge("structure_with_llm", "finalize")
    
    # Conditional edges (can go to different destinations based on state)
    workflow.add_conditional_edges("detect_type", route_from_node)        # -> extract_content OR finalize
    workflow.add_conditional_edges("process_images", route_from_node)     # -> structure_with_llm OR finalize
    workflow.add_conditional_edges("finalize", route_from_node)           # -> END
    
    # Compile graph
    return workflow.compile()