from langgraph.graph import StateGraph, END
from Agents.occurrence.state import OccurrenceState
from Agents.occurrence.nodes import generate_scores, calculate_weighted_score

# Define the graph
workflow = StateGraph(OccurrenceState)

# Add nodes
workflow.add_node("generate_scores", generate_scores)
workflow.add_node("calculate_weighted_score", calculate_weighted_score)

# Define edges
workflow.set_entry_point("generate_scores")
workflow.add_edge("generate_scores", "calculate_weighted_score")
workflow.add_edge("calculate_weighted_score", END)

# Compile graph
occurrence_graph = workflow.compile()
