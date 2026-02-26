import operator
from typing import TypedDict, Optional, List, Literal, Dict, Any, Annotated


def merge_dicts(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer to merge two dictionaries."""
    return {**existing, **new}


class RiskAssessmentState(TypedDict):
    """
    True Orchestrator State.
    Uses reducers to handle merging results from dynamic parallel workers.
    """

    # ── Inputs from the API request ─────────────────────────────────────────
    complaint_id: str                   # Unique complaint ID
    complaint_description: str          # Full description text
    source: str                         # e.g. "Customer", "Supplier Audit"
    date: str                           # e.g. "2024-01-15"
    product: str                        # Product name/model
    additional_context: str             # Extra context string
    similar_cases: List[Dict[str, Any]] # Historical similar cases

    # ── Execution Plan (from Orchestrator Brain) ────────────────────────────
    execution_plan: Dict[str, Any]      # Dynamic plan decided by LLM
    
    # ── Accumulators (with Reducers) ────────────────────────────────────────
    worker_results: Annotated[List[Dict[str, Any]], operator.add]
    orchestrator_log: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
    retry_counts: Annotated[Dict[str, int], merge_dicts]

    # ── Flags & Status ───────────────────────────────────────────────────────
    interrupt_signal: bool              # Signal to stop workers early
    replan_triggered: bool              # Signal to re-run orchestrator brain
    workflow_status: Optional[Literal["completed", "escalated", "halted"]]
    
    # ── Final Outputs ────────────────────────────────────────────────────────
    scores_valid: bool
    rpn_value: Optional[int]
    escalation_required: bool
    escalation_reason: str
    final_reasoning: str               # Synthesizer's intelligent explanation

    # Legacy fields (kept for backward compatibility during transition)
    severity_score: Optional[int]
    occurrence_score: Optional[int]
    detection_score: Optional[int]
    agent_outputs: Annotated[Dict[str, Any], merge_dicts]
    policy_path: Optional[str]
