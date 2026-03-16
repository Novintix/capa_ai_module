"""
LangGraph workflow for Ranking Agent.
Defines the state graph with 7 nodes for RCPS calculation and ranking.
"""

from langgraph.graph import StateGraph, END
from Agents.ranking.state import RankingState
from Agents.ranking.nodes import (
    calculate_rpn,
    normalize_rpn,
    evaluate_evidence,
    evaluate_mechanism,
    evaluate_proximity,
    calculate_rcps,
    rank_and_format
)


def create_ranking_graph():
    """
    Create and compile the Ranking Agent graph.
    
    Workflow:
        1. calculate_rpn: Calculate Risk Priority Number (S×O×D)
        2. normalize_rpn: Normalize RPN to 0-1 scale
        3. evaluate_evidence: Score evidence strength (LLM)
        4. evaluate_mechanism: Score mechanism fit (LLM)
        5. evaluate_proximity: Score causal proximity (LLM)
        6. calculate_rcps: Calculate weighted RCPS score
        7. rank_and_format: Sort and format final output
    
    Returns:
        Compiled StateGraph ready for invocation
    """
    workflow = StateGraph(RankingState)
    
    # Add nodes
    workflow.add_node("calculate_rpn", calculate_rpn)
    workflow.add_node("normalize_rpn", normalize_rpn)
    workflow.add_node("evaluate_evidence", evaluate_evidence)
    workflow.add_node("evaluate_mechanism", evaluate_mechanism)
    workflow.add_node("evaluate_proximity", evaluate_proximity)
    workflow.add_node("calculate_rcps", calculate_rcps)
    workflow.add_node("rank_and_format", rank_and_format)
    
    # Set entry point
    workflow.set_entry_point("calculate_rpn")
    
    # Define edges (linear flow)
    workflow.add_edge("calculate_rpn", "normalize_rpn")
    workflow.add_edge("normalize_rpn", "evaluate_evidence")
    workflow.add_edge("evaluate_evidence", "evaluate_mechanism")
    workflow.add_edge("evaluate_mechanism", "evaluate_proximity")
    workflow.add_edge("evaluate_proximity", "calculate_rcps")
    workflow.add_edge("calculate_rcps", "rank_and_format")
    workflow.add_edge("rank_and_format", END)
    
    return workflow.compile()


# Export compiled graph
ranking_graph = create_ranking_graph()
