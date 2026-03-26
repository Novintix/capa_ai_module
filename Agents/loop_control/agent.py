"""
Loop Control agent interface.
"""

from typing import Any, Dict

from Agents.loop_control.graph import create_loop_control_graph
from Agents.loop_control.state import LoopControlInput


class LoopControlAgent:
	"""
	Main interface for Loop Control analysis.
	"""

	def __init__(self):
		self.graph = create_loop_control_graph()

	def evaluate(self, payload: LoopControlInput) -> Dict[str, Any]:
		initial_state = {
			"input": payload,
			"chain_health": None,
			"root_cause_score": None,
			"loop_signals": None,
			"decision": None,
			"reasoning": None,
			"next_step": None,
			"final_output": None,
		}

		result = self.graph.invoke(initial_state)
		final_output = result.get("final_output")
		if final_output is None:
			raise ValueError("Loop Control agent failed to produce final output")

		return final_output.model_dump()

