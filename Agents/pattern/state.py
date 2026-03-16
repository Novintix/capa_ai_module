from typing import TypedDict, List, Optional, Dict, Any


class AgentState(TypedDict):
    """
    State for the Pattern Agent.
    """

    # ── Inputs ────────────────────────────────────────────────
    complaint_id: str
    complaint_description: str

    # Optional complaint context — used for richer mongo filtering
    # if provided by the caller (orchestrator or API request)
    product_family: Optional[str]
    region: Optional[str]
    severity: Optional[str]
    site: Optional[str]

    # ── Tenant context ────────────────────────────────────────
    company_id: Optional[str]          # identifies the tenant
    company_schema: Optional[Dict]     # resolved schema from orchestrator
                                       # None = use generic field aliases

    # ── Internal / derived ───────────────────────────────────
    failure_class: Optional[str]       # detected failure class from description
                                       # e.g. "Software/Firmware Failure"
    historical_complaints: List[Dict]  # raw records fetched from MongoDB

    # ── Outputs ───────────────────────────────────────────────
    trend_score: Optional[int]
    trend_category: Optional[str]
    confidence: Optional[float]
    explanation: Optional[str]
    matched_complaint_ids: List[str]   # IDs of all semantically matched records
    identified_pattern: Optional[str]  # one-line pattern summary

    # ── Workflow control ──────────────────────────────────────
    iteration: int
    max_iterations: int
    error: Optional[str]
    next_step: str