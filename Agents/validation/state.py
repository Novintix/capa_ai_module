"""
Validation Agent State
TypedDict for LangGraph state management
"""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
	"""
	State for Validation Agent
	Uses total=False to allow dynamic fields
	"""

	# Input fields
	complaint_id: Optional[str]
	question: Optional[str]
	complaint_description: str
	generated_causes: List[Dict[str, Any]]
	logs: Any
	reports: Any
	process_data: Any
	historical_capa: Any
	policies: Any
	sop: Any
	investigation_records: Any
	investigation_evidence: Any
	supporting_system_information: Any

	# Processing fields
	evidence_records: List[Dict[str, Any]]
	file_evidence_records: List[Dict[str, Any]]
	evidence_chunk_count: int           # number of chunks indexed by semantic_retriever
	cause_validation_results: List[Dict[str, Any]]
	validated_causes: List[Dict[str, Any]]

	# Output fields
	total_input_causes: int
	total_validated_causes: int
	overall_confidence: float
	notes: Optional[str]

	# Control fields
	iteration: int
	max_iterations: int
	next_step: str
	error: Optional[str]
