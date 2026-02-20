from langgraph.graph import StateGraph, END
from Agents.occurrence.state import OccurrenceState
from Agents.occurrence.nodes import prepare_evidence, generate_scores, calculate_weighted_score

# DO #5: Graph construction is separate from node logic
# DO #4: Explicit path to END — every node has a guaranteed route to termination
workflow = StateGraph(OccurrenceState)

# Add nodes — each does exactly one job (DO #2)
workflow.add_node("prepare_evidence", prepare_evidence)
workflow.add_node("generate_scores", generate_scores)
workflow.add_node("calculate_weighted_score", calculate_weighted_score)

# Define edges — routing is explicit and readable (DO #3)
workflow.set_entry_point("prepare_evidence")
workflow.add_edge("prepare_evidence", "generate_scores")

def should_retry(state: OccurrenceState):
    """
    Check if we have scores. If yes, proceed. 
    If no (LLM failure), retry generate_scores (up to MAX_RETRIES handled in node).
    """
    if state.raw_scores:
        return "calculate_weighted_score"
    return "generate_scores"

workflow.add_conditional_edges(
    "generate_scores",
    should_retry,
    {
        "calculate_weighted_score": "calculate_weighted_score",
        "generate_scores": "generate_scores"
    }
)
workflow.add_edge("calculate_weighted_score", END)

# Compile graph
occurrence_graph = workflow.compile()
