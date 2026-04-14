"""
Internal state model for Root Cause Analysis coordinator.

Phases (3 HITL points only):
  idle
  fishbone_running              -- fishbone started; internal HITL handled by /fishbone-v3/decide
  awaiting_category_selection   -- fishbone fully done; user picks a category (HITL #2)
  why_running                   -- why analysis started; internal HITL handled by /why-analysis-v3/human-review
  awaiting_action_plan_confirmation -- why fully done; user confirms proceed to action plan (HITL #3)
  completed
  error
"""

from typing import Any, Dict, List, Optional, TypedDict


class RCASessionState(TypedDict, total=False):
    complaint_id: str
    phase: str
    selected_method: str
    message: str

    # Original request payload from start endpoint
    original_input: Dict[str, Any]

    # Fishbone stage snapshot (initial output from analyze(); full final from session on select-category)
    fishbone_output: Optional[Dict[str, Any]]
    available_categories: List[str]
    selected_category: Optional[str]

    # Why stage snapshot
    why_output: Optional[Dict[str, Any]]
    why_session_id: Optional[str]

    # Final handoff
    action_plan_ready: bool
    action_plan_endpoint: str

    # Coordination metadata
    next_action: Optional[str]
    error: Optional[str]
    updated_at: float
    audit_log: List[Dict[str, Any]]
