from typing import TypedDict, Optional, Any, Dict


class DirectorState(TypedDict):

    # ── Input ────────────────────────────────────────────────────────────────
    complaint_id:        str
    complaint:           str
    evidence:            Optional[str]
    sop:                 Optional[str]
    fmea_document_path:  Optional[str]
    thread_id:           Optional[str]
    max_rca_depth:       int

    # ── Agent outputs (unchanged — same as before) ───────────────────────────
    risk_analysis_output: Optional[Dict[str, Any]]
    rca_output:           Optional[Dict[str, Any]]
    action_plan_output:   Optional[Dict[str, Any]]
    effectiveness_output: Optional[Dict[str, Any]]

    # ── Agent context (unchanged) ────────────────────────────────────────────
    containment_actions: str
    timeline_constraint: str
    available_resources: str
    system_context:      str

    # ── Director brain (NEW) ─────────────────────────────────────────────────
    next_agent:          str            # Which agent O1 wants to call next
    director_reasoning:  str            # Why O1 made this decision (visible to human)
    rca_mode:            str            # "standard" | "deep" — O1 adjusts RCA depth
    rca_retry_count:     int            # How many times O1 has re-run RCA
    plan_retry_count:    int            # How many times O1 has re-run Action Plan

    # ── Human-in-the-loop ────────────────────────────────────────────────────
    human_approved:  Optional[bool]
    human_feedback:  Optional[str]

    # ── Error recovery ───────────────────────────────────────────────────────
    failed_node:    Optional[str]
    retry_count:    int
    max_retries:    int
    recovery_next:  Optional[str]

    # ── Flow ─────────────────────────────────────────────────────────────────
    status: str
    error:  Optional[str]