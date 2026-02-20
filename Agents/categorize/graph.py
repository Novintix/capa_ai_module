from langgraph.graph import StateGraph, END
from Agents.categorize.state import CategorizeState
from Agents.categorize.nodes import categorize_causes, build_output

workflow = StateGraph(CategorizeState)

workflow.add_node("categorize_causes", categorize_causes)
workflow.add_node("build_output", build_output)

workflow.set_entry_point("categorize_causes")

def should_retry(state: CategorizeState):
    """Check if we have categorizations. If yes, proceed. If no, retry."""
    if state.raw_categorizations:
        return "build_output"
    return "categorize_causes"

workflow.add_conditional_edges(
    "categorize_causes",
    should_retry,
    {
        "build_output": "build_output",
        "categorize_causes": "categorize_causes"
    }
)

workflow.add_edge("build_output", END)

categorize_graph = workflow.compile()
