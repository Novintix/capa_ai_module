"""
State model for Why Analysis V3 orchestrator.

Simplified flow: question -> causes -> validation -> human_review -> (if 0 causes) zero_evidence
"""

import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


class WhyChainEntry(TypedDict, total=False):
    """One completed RCA loop entry."""
    loop: int
    question: str
    selected_cause: str
    selected_cause_id: str
    confidence: float
    human_approved: bool


class WhyAnalysisV3State(TypedDict, total=False):
    """LangGraph state for Why Analysis V3."""

    # ── Input ─────────────────────────────────────────────────────────────────
    complaint_id: str
    complaint: str
    evidence: str
    sop: str
    fmea_document_path: Optional[str]
    session_id: Optional[str]
    evidence_files: Optional[List[str]]
    logs: Optional[Any]
    reports: Optional[Any]
    process_data: Optional[Any]
    historical_capa: Optional[Any]
    policies: Optional[Any]
    investigation_records: Optional[Any]
    supporting_system_information: Optional[Any]

    # ── Runtime ───────────────────────────────────────────────────────────────
    start_time: float
    has_fmea: bool
    mode: str
    current_loop_count: int
    agent_payloads: Dict[str, Any]  # Built by payload_builder_node
    current_why_question: Optional[str]
    current_why_reasoning: Optional[str]
    current_question_input: Dict[str, Any]
    current_question_result: Dict[str, Any]
    
    # ── Cause Generation ──────────────────────────────────────────────────────
    current_causes: List[Dict[str, Any]]
    current_total_causes: int
    current_fmea_matched: int
    current_cause_generation_input: Dict[str, Any]
    current_cause_generation_result: Dict[str, Any]
    
    # ── Validation ────────────────────────────────────────────────────────────
    current_validation_input: Dict[str, Any]
    current_validation_result: Dict[str, Any]
    validation_result: Dict[str, Any]
    validated_causes_enriched: List[Dict[str, Any]]
    
    # ── Human Review ──────────────────────────────────────────────────────────
    awaiting_human_review: bool
    human_review_message: Optional[str]
    human_selected_cause_id: Optional[str]
    human_decision: Optional[str]  # "root_cause" or "continue"
    current_selected_cause: Optional[Dict[str, Any]]
    current_cause_confidence: float
    
    # ── Zero Evidence ─────────────────────────────────────────────────────────
    current_zero_evidence_input: Dict[str, Any]
    current_zero_evidence_result: Dict[str, Any]
    zero_evidence_result: Dict[str, Any]

    # ── History and final result ──────────────────────────────────────────────
    why_chain: List[WhyChainEntry]
    iteration_outputs: List[Dict[str, Any]]
    final_root_cause: Optional[Dict[str, Any]]
    ai_flagged: bool
    manual_investigation_required: bool
    stopping_reason: Optional[str]

    # ── Flow control ──────────────────────────────────────────────────────────
    status: str
    error: Optional[str]
    next_step: Optional[str]
    final_output: Dict[str, Any]

    # ── Observability ─────────────────────────────────────────────────────────
    node_log: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[Dict[str, Any]], operator.add]
