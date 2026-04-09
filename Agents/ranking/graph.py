"""
LangGraph workflow for Ranking Agent.
Defines the state graph with 5 nodes for RCPS calculation and ranking.

Node count reduced from 7 → 5 by merging the 3 sequential LLM evaluation
nodes into a single evaluate_all_scores node.
"""

from langgraph.graph import StateGraph, END
from Agents.ranking.state import RankingState
from Agents.ranking.nodes import (
    calculate_rpn,
    normalize_rpn,
    evaluate_all_scores,
    calculate_rcps,
    rank_and_format
)


def create_ranking_graph():
    """
    Create and compile the Ranking Agent graph.

    Workflow (5 nodes, reduced from 7):
        1. calculate_rpn       : Calculate Risk Priority Number (S×O×D)
        2. normalize_rpn       : Normalize RPN to 0-1 scale
        3. evaluate_all_scores : Score evidence + mechanism + proximity in ONE LLM call per cause
        4. calculate_rcps      : Calculate weighted RCPS score
        5. rank_and_format     : Sort and format final output

    Returns:
        Compiled StateGraph ready for invocation
    """
    workflow = StateGraph(RankingState)

    # Add nodes
    workflow.add_node("calculate_rpn",       calculate_rpn)
    workflow.add_node("normalize_rpn",       normalize_rpn)
    workflow.add_node("evaluate_all_scores", evaluate_all_scores)
    workflow.add_node("calculate_rcps",      calculate_rcps)
    workflow.add_node("rank_and_format",     rank_and_format)

    # Set entry point
    workflow.set_entry_point("calculate_rpn")

    # Linear flow — 3 evaluation nodes collapsed into 1
    workflow.add_edge("calculate_rpn",       "normalize_rpn")
    workflow.add_edge("normalize_rpn",       "evaluate_all_scores")
    workflow.add_edge("evaluate_all_scores", "calculate_rcps")
    workflow.add_edge("calculate_rcps",      "rank_and_format")
    workflow.add_edge("rank_and_format",     END)

    return workflow.compile()


# Export compiled graph
ranking_graph = create_ranking_graph()
