"""
state.py

Defines ActionPlanState for CAPA Action Plan LangGraph workflow.
"""

from typing import TypedDict, Optional, List


class ActionPlanState(TypedDict, total=False):
    """State passed through action plan graph nodes"""
    
    # ── Input (explicit fields matching CapaInput schema) ────────────────────
    investigation_summary: str
    containment_actions: str
    five_why_analysis: str
    primary_root_cause: str
    contributing_root_causes: Optional[List[str]]
    systemic_root_causes: Optional[List[str]]
    evidence_collected: str
    root_cause_verification_status: str
    severity_level: Optional[str]
    timeline_constraint: Optional[str]
    available_resources: Optional[str]
    
    # ── Processing (output fields) ───────────────────────────────────────────
    action_items: Optional[List[dict]]
    total_actions: Optional[int]
    primary_actions: Optional[int]
    preventive_systemic_actions: Optional[int]
    confidence_score: Optional[float]
    notes: Optional[str]
    
    # ── Error tracking ────────────────────────────────────────────────────────
    error: Optional[str]
