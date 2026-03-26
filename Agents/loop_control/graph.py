"""
LangGraph workflow for Loop Control agent.
"""

from langgraph.graph import END, StateGraph

from Agents.loop_control.nodes import decide_node, evaluate_chain_node, finalize_output_node
from Agents.loop_control.state import LoopControlState


def create_loop_control_graph():
	workflow = StateGraph(LoopControlState)

	workflow.add_node("evaluate_chain", evaluate_chain_node)
	workflow.add_node("decide", decide_node)
	workflow.add_node("finalize_output", finalize_output_node)

	workflow.set_entry_point("evaluate_chain")
	workflow.add_edge("evaluate_chain", "decide")
	workflow.add_edge("decide", "finalize_output")
	workflow.add_edge("finalize_output", END)

	return workflow.compile()

