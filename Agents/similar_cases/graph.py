"""
LangGraph workflow for Similar Cases Agent.
Defines the state graph with 3 nodes: embed_query → vector_search → format_results
"""

from langgraph.graph import StateGraph, END
from Agents.similar_cases.state import SimilarCasesState
from Agents.similar_cases.nodes import embed_query, vector_search, format_results


def create_similar_cases_graph():
    """
    Create and compile the Similar Cases Agent graph.
    
    Workflow:
        1. embed_query: Convert user query to embedding vector
        2. vector_search: Search MongoDB for similar cases
        3. format_results: Format and return final output
    
    Returns:
        Compiled StateGraph ready for invocation
    """
    workflow = StateGraph(SimilarCasesState)
    
    # Add nodes
    workflow.add_node("embed_query", embed_query)
    workflow.add_node("vector_search", vector_search)
    workflow.add_node("format_results", format_results)
    
    # Set entry point
    workflow.set_entry_point("embed_query")
    
    # Define edges (linear flow)
    workflow.add_edge("embed_query", "vector_search")
    workflow.add_edge("vector_search", "format_results")
    workflow.add_edge("format_results", END)
    
    return workflow.compile(name="A1_similar_cases_agent")


# Export compiled graph
similar_cases_graph = create_similar_cases_graph()
