"""
State model for Why Analysis V2 orchestrator.
"""

from typing import Any, Dict, List, Optional, TypedDict


class WhyChainEntry(TypedDict, total=False):
    """One completed RCA loop entry."""

    loop: int
    question: str
    selected_cause: str
    selected_cause_id: str
    confidence: float
    selection_path: str
    loop_decision: Optional[str]
    loop_reasoning: Optional[str]


class WhyAnalysisV2State(TypedDict, total=False):
    """LangGraph state for Why Analysis V2."""

    # Input
    complaint_id: str
    complaint: str
    evidence: str
    sop: str
    fmea_document_path: Optional[str]
    max_loops: int
    session_id: Optional[str]
    evidence_files: Optional[List[str]]
    logs: Optional[Any]
    reports: Optional[Any]
    process_data: Optional[Any]
    historical_capa: Optional[Any]
    policies: Optional[Any]
    investigation_records: Optional[Any]
    supporting_system_information: Optional[Any]

    # Runtime
    start_time: float
    has_fmea: bool
    mode: str
    current_loop_count: int
    current_why_question: Optional[str]
    current_why_reasoning: Optional[str]
    current_question_input: Dict[str, Any]
    current_question_result: Dict[str, Any]
    current_causes: List[Dict[str, Any]]
    current_total_causes: int
    current_fmea_matched: int
    current_cause_generation_input: Dict[str, Any]
    current_cause_generation_result: Dict[str, Any]
    current_selected_cause: Optional[Dict[str, Any]]
    current_cause_confidence: float
    current_selection_path: str
    current_validation_input: Dict[str, Any]
    current_validation_result: Dict[str, Any]
    current_ranking_input: Dict[str, Any]
    current_ranking_result: Dict[str, Any]
    current_zero_evidence_input: Dict[str, Any]
    current_zero_evidence_result: Dict[str, Any]
    current_loop_control_input: Dict[str, Any]

    # Validation and ranking
    validation_result: Dict[str, Any]
    validated_causes_enriched: List[Dict[str, Any]]
    ranking_result: Dict[str, Any]
    zero_evidence_result: Dict[str, Any]
    loop_control_result: Dict[str, Any]

    # History and final result
    why_chain: List[WhyChainEntry]
    iteration_outputs: List[Dict[str, Any]]
    final_root_cause: Optional[Dict[str, Any]]
    ai_flagged: bool
    manual_investigation_required: bool
    stopping_reason: Optional[str]

    # Flow control
    status: str
    error: Optional[str]
    next_step: Optional[str]
    final_output: Dict[str, Any]

    # Observability — session tracking and node audit trail
    node_log: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
