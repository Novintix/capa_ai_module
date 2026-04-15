"""
LangGraph state model for Root Cause Analysis coordinator.

Phases:
  idle
  running                           -- graph started, initializing
  fishbone_running                  -- fishbone orchestrator called
  awaiting_category_selection       -- HITL #2 pause: user picks a fishbone category
  category_selected                 -- category validated, proceeding to Why
  why_awaiting_review               -- why orchestrator returned, awaiting human review
  awaiting_action_plan_confirmation -- HITL #3 pause: user confirms action plan
  processing                        -- async timeout, still running in background
  completed
  error
"""

import operator
import time
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import TypedDict


class RCAGraphState(TypedDict, total=False):
    """LangGraph state for Root Cause Analysis coordinator."""

    # ── Input ──────────────────────────────────────────────────────────────────
    complaint_id: str
    complaint: str
    evidence: str
    sop: str
    fmea_document_path: Optional[str]
    method: str  # "why" or "fishbone"
    evidence_files: Optional[List[str]]
    logs: Optional[Any]
    reports: Optional[Any]
    process_data: Optional[Any]
    historical_capa: Optional[Any]
    policies: Optional[Any]
    investigation_records: Optional[Any]
    supporting_system_information: Optional[Any]
    original_input: Dict[str, Any]

    # ── Runtime ────────────────────────────────────────────────────────────────
    session_id: Optional[str]
    start_time: float
    phase: str

    # ── Fishbone stage ─────────────────────────────────────────────────────────
    fishbone_output: Optional[Dict[str, Any]]
    available_categories: List[str]
    # Evidence enriched with fishbone category context (passed into Why Analysis)
    enriched_evidence: Optional[str]

    # ── HITL #2 — user-provided via POST /rca/select-category ─────────────────
    selected_category: Optional[str]
    selected_cause_id: Optional[str]
    selected_cause_text: Optional[str]

    # ── Why stage ──────────────────────────────────────────────────────────────
    why_output: Optional[Dict[str, Any]]
    why_session_id: Optional[str]

    # ── HITL #3 — user-provided via POST /rca/proceed-action-plan ─────────────
    action_plan_confirmed: Optional[bool]

    # ── Final stage ────────────────────────────────────────────────────────────
    action_plan_ready: bool
    action_plan_endpoint: str

    # ── Control ────────────────────────────────────────────────────────────────
    next_action: Optional[str]
    error: Optional[str]
    message: Optional[str]
    updated_at: float

    # ── Observability (append-only lists) ─────────────────────────────────────
    audit_log: Annotated[List[Dict[str, Any]], operator.add]
    node_log: Annotated[List[Dict[str, Any]], operator.add]

    # ── Final response dict written by finalize_node ───────────────────────────
    final_output: Optional[Dict[str, Any]]
