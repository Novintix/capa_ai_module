"""
Validation Agent Graph
LangGraph workflow definition
"""

from langgraph.graph import END, StateGraph

from .nodes import (
	filter_validated_node,
	finalize_node,
	initialize_node,
	prepare_evidence_node,
	validate_causes_node,
)
from .state import AgentState


def create_validation_graph():
	"""
	Create validation workflow graph.

	Flow:
	1. initialize -> prepare_evidence
	2. prepare_evidence -> validate_causes OR finalize
	3. validate_causes -> filter_validated OR finalize
	4. filter_validated -> finalize
	5. finalize -> END
	"""

	workflow = StateGraph(AgentState)

	workflow.add_node("initialize", initialize_node)
	workflow.add_node("prepare_evidence", prepare_evidence_node)
	workflow.add_node("validate_causes", validate_causes_node)
	workflow.add_node("filter_validated", filter_validated_node)
	workflow.add_node("finalize", finalize_node)

	workflow.set_entry_point("initialize")

	def route_from_node(state: AgentState):
		next_step = state.get("next_step", "end")
		if next_step == "end":
			return END
		return next_step

	workflow.add_edge("initialize", "prepare_evidence")
	workflow.add_edge("filter_validated", "finalize")

	workflow.add_conditional_edges("prepare_evidence", route_from_node)
	workflow.add_conditional_edges("validate_causes", route_from_node)
	workflow.add_conditional_edges("finalize", route_from_node)

	return workflow.compile()
