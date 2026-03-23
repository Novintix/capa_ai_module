"""
Validation Agent
Main agent class for validating generated causes against investigation evidence
"""

from typing import Any, Dict

from .graph import create_validation_graph
from .logger import log_error
from .schemas import ValidationInput


class ValidationAgent:
	"""
	Validation Agent using LangGraph.

	Responsibilities:
	- Evaluate each generated cause against evidence corpus
	- Return evidence match status for each cause
	- Return only evidence-grounded causes in validated output

	Does NOT:
	- Generate new causes
	- Replace SME review for borderline causes
	"""

	def __init__(self):
		self.graph = create_validation_graph()

	def validate_causes(self, validation_input: ValidationInput) -> Dict[str, Any]:
		"""
		Validate generated causes against complaint and investigation evidence.
		"""
		try:
			initial_state = {
				"complaint_id": validation_input.complaint_id,
				"question": validation_input.question,
				"generated_causes": [cause.model_dump() for cause in validation_input.generated_causes],
				"complaint_description": validation_input.complaint_description,
				"logs": validation_input.logs,
				"reports": validation_input.reports,
				"process_data": validation_input.process_data,
				"historical_capa": validation_input.historical_capa,
				"policies": validation_input.policies,
				"sop": validation_input.sop,
				"investigation_records": validation_input.investigation_records,
				"investigation_evidence": validation_input.investigation_evidence,
				"supporting_system_information": validation_input.supporting_system_information,
			}

			final_state = self.graph.invoke(initial_state)

			if final_state.get("error"):
				return {
					"complaint_id": validation_input.complaint_id,
					"complaint_description": validation_input.complaint_description,
					"total_input_causes": len(validation_input.generated_causes),
					"total_validated_causes": 0,
					"validated_causes": [],
					"cause_validation_results": final_state.get("cause_validation_results", []),
					"overall_confidence": 0.0,
					"notes": f"Error: {final_state['error']}",
				}

			return {
				"complaint_id": final_state.get("complaint_id"),
				"complaint_description": final_state.get("complaint_description"),
				"total_input_causes": final_state.get("total_input_causes", len(validation_input.generated_causes)),
				"total_validated_causes": final_state.get("total_validated_causes", 0),
				"validated_causes": final_state.get("validated_causes", []),
				"cause_validation_results": final_state.get("cause_validation_results", []),
				"overall_confidence": final_state.get("overall_confidence", 0.0),
				"notes": final_state.get("notes"),
			}

		except Exception as exc:
			log_error("validate_causes", str(exc))
			return {
				"complaint_id": validation_input.complaint_id,
				"complaint_description": validation_input.complaint_description,
				"total_input_causes": len(validation_input.generated_causes),
				"total_validated_causes": 0,
				"validated_causes": [],
				"cause_validation_results": [],
				"overall_confidence": 0.0,
				"notes": f"Agent error: {exc}",
			}
