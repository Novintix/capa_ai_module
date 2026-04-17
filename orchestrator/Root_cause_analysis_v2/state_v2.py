"""
LangGraph state model for unified RCA v2.

v2 goals:
- Single parent orchestrator handles Fishbone + Why flow directly.
- Redis checkpointed HITL sessions via LangGraph thread_id=session_id.
- Two HITL gates:
  1) fishbone cause selection
  2) why decision (continue/root_cause)
"""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional

from typing_extensions import TypedDict


class RCACausePayload(TypedDict, total=False):
  cause_id: str
  cause_text: str
  process_step: Optional[str]
  failure_mode: Optional[str]
  potential_effects: Optional[str]
  severity: Optional[int]
  occurrence: Optional[int]
  detection: Optional[int]
  current_controls: Optional[str]
  source: Optional[str]
  category: Optional[str]
  category_confidence: Optional[float]
  category_reasoning: Optional[str]
  secondary_categories: List[str]
  validation_status: Optional[str]
  validation_confidence: Optional[float]
  validation_rationale: Optional[str]


class WhyQuestionStartInputState(TypedDict, total=False):
  complaint_id: str
  complaint: str
  evidence: str
  sop: str


class WhyQuestionContinueInputState(TypedDict, total=False):
  complaint_id: str
  answer: str


class WhyQuestionOutputState(TypedDict, total=False):
  complaint_id: Optional[str]
  why_question: Optional[str]
  reasoning: Optional[str]
  why_depth: Optional[int]
  error: Optional[str]


class CauseGenerationInputState(TypedDict, total=False):
  question_id: str
  question: str
  context: Optional[str]
  evidence_context: Optional[Dict[str, Any]]
  fmea_document_path: Optional[str]


class CauseGenerationOutputState(TypedDict, total=False):
  question_id: str
  question: str
  causes: List[RCACausePayload]
  total_causes: int
  fmea_document_used: str
  matched_entries: int
  evidence_extracted: Optional[int]
  confidence: float
  notes: Optional[str]


class CategorizeInputCauseState(TypedDict, total=False):
  cause_id: str
  cause_text: str
  process_step: Optional[str]
  failure_mode: Optional[str]
  potential_effects: Optional[str]
  severity: Optional[int]
  occurrence: Optional[int]
  detection: Optional[int]
  current_controls: Optional[str]
  source: Optional[str]


class CategorizeInputState(TypedDict, total=False):
  question: str
  causes: List[CategorizeInputCauseState]
  additional_context: Optional[str]


class CategorizedCauseState(TypedDict, total=False):
  cause_id: str
  cause_text: str
  category: str
  confidence: float
  secondary_categories: List[str]
  reasoning: str


class CategorizeOutputState(TypedDict, total=False):
  categorized_causes: List[CategorizedCauseState]
  summary: Dict[str, int]


class ValidationGeneratedCauseState(TypedDict, total=False):
  cause_id: str
  cause_text: str
  process_step: Optional[str]
  failure_mode: Optional[str]
  potential_effects: Optional[str]
  severity: Optional[int]
  occurrence: Optional[int]
  detection: Optional[int]
  current_controls: Optional[str]
  source: Optional[str]


class ValidationInputState(TypedDict, total=False):
  complaint_id: Optional[str]
  question: Optional[str]
  generated_causes: List[ValidationGeneratedCauseState]
  complaint_description: str
  logs: Optional[Any]
  reports: Optional[Any]
  process_data: Optional[Any]
  historical_capa: Optional[Any]
  policies: Optional[Any]
  sop: Optional[Any]
  investigation_records: Optional[Any]
  supporting_system_information: Optional[Any]
  investigation_evidence: Optional[Any]


class ValidationCauseResultState(TypedDict, total=False):
  cause_id: str
  cause_text: str
  process_step: Optional[str]
  failure_mode: Optional[str]
  potential_effects: Optional[str]
  severity: Optional[int]
  occurrence: Optional[int]
  detection: Optional[int]
  current_controls: Optional[str]
  source: Optional[str]
  evidence_match_status: Literal["matched", "partially_matched", "no_evidence"]
  supporting_evidence_references: List[str]
  confidence: float
  rationale: str


class ValidationOutputState(TypedDict, total=False):
  complaint_id: Optional[str]
  complaint_description: str
  total_input_causes: int
  total_validated_causes: int
  validated_causes: List[ValidationCauseResultState]
  cause_validation_results: List[ValidationCauseResultState]
  overall_confidence: float
  notes: Optional[str]


class ZeroEvidenceCauseInputState(TypedDict, total=False):
  cause_id: str
  cause_text: str
  process_step: Optional[str]
  failure_mode: Optional[str]
  potential_effects: Optional[str]
  severity: Optional[int]
  occurrence: Optional[int]
  detection: Optional[int]
  current_controls: Optional[str]
  source: Optional[str]
  category: Optional[str]


class ZeroEvidenceInputState(TypedDict, total=False):
  question_id: Optional[str]
  complaint_id: Optional[str]
  question: str
  complaint_description: Optional[str]
  investigation_evidence: Optional[str]
  causes: List[ZeroEvidenceCauseInputState]
  total_causes: Optional[int]


class ZeroEvidenceSelectedRootCauseState(TypedDict, total=False):
  cause_id: str
  cause_text: str
  process_step: str
  reason: str


class ZeroEvidenceOutputState(TypedDict, total=False):
  selected_root_cause: Optional[ZeroEvidenceSelectedRootCauseState]
  confidence: float
  error: Optional[str]


class WhyQuestionCallState(TypedDict, total=False):
  depth: int
  mode: Literal["start", "continue"]
  input: Dict[str, Any]
  output: Dict[str, Any]


class WhyCauseGenerationCallState(TypedDict, total=False):
  depth: int
  input: CauseGenerationInputState
  output: CauseGenerationOutputState


class WhyValidationCallState(TypedDict, total=False):
  depth: int
  input: ValidationInputState
  output: ValidationOutputState


class WhyZeroEvidenceCallState(TypedDict, total=False):
  depth: int
  input: ZeroEvidenceInputState
  output: ZeroEvidenceOutputState


class RCAV2GraphState(TypedDict, total=False):
    # Input
    complaint_id: str
    complaint: str
    evidence: str
    sop: str
    fmea_document_path: Optional[str]
    method: str  # why | fishbone
    evidence_files: Optional[List[str]]
    logs: Optional[Any]
    reports: Optional[Any]
    process_data: Optional[Any]
    historical_capa: Optional[Any]
    policies: Optional[Any]
    investigation_records: Optional[Any]
    supporting_system_information: Optional[Any]

    # Agent payload schemas: Fishbone
    fishbone_cause_generation_input: Optional[CauseGenerationInputState]
    fishbone_cause_generation_output: Optional[CauseGenerationOutputState]
    fishbone_categorize_input: Optional[CategorizeInputState]
    fishbone_categorize_output: Optional[CategorizeOutputState]
    fishbone_validation_input: Optional[ValidationInputState]
    fishbone_validation_output: Optional[ValidationOutputState]
    fishbone_zero_evidence_input: Optional[ZeroEvidenceInputState]
    fishbone_zero_evidence_output: Optional[ZeroEvidenceOutputState]

    # Agent payload schemas: Why
    why_question_start_input: Optional[WhyQuestionStartInputState]
    why_question_continue_input: Optional[WhyQuestionContinueInputState]
    why_question_output: Optional[WhyQuestionOutputState]
    why_cause_generation_input: Optional[CauseGenerationInputState]
    why_cause_generation_output: Optional[CauseGenerationOutputState]
    why_validation_input: Optional[ValidationInputState]
    why_validation_output: Optional[ValidationOutputState]
    why_zero_evidence_input: Optional[ZeroEvidenceInputState]
    why_zero_evidence_output: Optional[ZeroEvidenceOutputState]

    # Runtime
    session_id: str
    question_agent_session_id: str
    start_time: float
    updated_at: float
    phase: str
    status: str
    message: Optional[str]
    error: Optional[str]
    next_action: Optional[str]
    awaiting_human_review: bool
    hitl_type: Optional[str]  # fishbone | why
    stopping_reason: Optional[str]
    ai_flagged: bool

    # Shared problem context for why loop
    active_problem_text: str

    # Fishbone pipeline outputs
    fishbone_all_causes: List[Dict[str, Any]]
    fishbone_categorized_causes: List[Dict[str, Any]]
    fishbone_validated_causes: List[Dict[str, Any]]
    fishbone_qualified_causes: List[Dict[str, Any]]
    fishbone_candidate_causes: List[Dict[str, Any]]
    fishbone_category_summary: Dict[str, int]
    fishbone_zero_evidence_result: Optional[Dict[str, Any]]
    fishbone_recommended_cause_id: Optional[str]

    # Fishbone HITL input
    fishbone_selected_cause_id: Optional[str]

    # Why pipeline outputs
    why_depth: int
    current_why_question: Optional[str]
    why_current_causes: List[Dict[str, Any]]
    why_validated_causes: List[Dict[str, Any]]
    why_qualified_causes: List[Dict[str, Any]]
    why_candidate_causes: List[Dict[str, Any]]
    why_requires_zero_evidence: bool

    # Why HITL input
    why_selected_cause_id: Optional[str]
    why_human_decision: Optional[str]  # continue | root_cause

    # Final result
    final_root_cause: Optional[Dict[str, Any]]

    # History for UI
    why_chain: Annotated[List[Dict[str, Any]], operator.add]
    why_iterations: Annotated[List[Dict[str, Any]], operator.add]
    why_question_calls: Annotated[List[WhyQuestionCallState], operator.add]
    why_cause_generation_calls: Annotated[List[WhyCauseGenerationCallState], operator.add]
    why_validation_calls: Annotated[List[WhyValidationCallState], operator.add]
    why_zero_evidence_calls: Annotated[List[WhyZeroEvidenceCallState], operator.add]
    timeline: Annotated[List[Dict[str, Any]], operator.add]
    audit_log: Annotated[List[Dict[str, Any]], operator.add]
    node_log: Annotated[List[Dict[str, Any]], operator.add]

    # Final response payload
    final_output: Optional[Dict[str, Any]]
