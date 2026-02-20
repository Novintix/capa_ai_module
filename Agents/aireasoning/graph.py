from langgraph.graph import StateGraph, END
from Agents.aireasoning.state import AIReasoningState
from Agents.aireasoning.nodes import prepare_evidence, generate_reasoning, finalize_output

workflow = StateGraph(AIReasoningState)

# Add nodes
workflow.add_node("prepare_evidence", prepare_evidence)
workflow.add_node("generate_reasoning", generate_reasoning)
workflow.add_node("finalize_output", finalize_output)

# Define edges
workflow.set_entry_point("prepare_evidence")
workflow.add_edge("prepare_evidence", "generate_reasoning")
workflow.add_edge("generate_reasoning", "finalize_output")
workflow.add_edge("finalize_output", END)

# Compile graph
aireasoning_graph = workflow.compile()
