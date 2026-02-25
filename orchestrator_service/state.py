import operator
from typing import TypedDict, Optional, List, Literal, Dict, Any, Annotated


def merge_dicts(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer to merge two dictionaries."""
    return {**existing, **new}


class RiskAssessmentState(TypedDict):
    """
    Single shared state passed through every node in the LangGraph graph.
    Each node reads what it needs and writes back only its results.
    """

    # ── Inputs from the API request ─────────────────────────────────────────
    complaint_id: str                   # Unique complaint ID
    complaint_description: str          # Full description text

    # Occurrence + Detection specific inputs
    source: str                         # e.g. "Customer", "Supplier Audit"
    date: str                           # e.g. "2024-01-15"
    product: str                        # Product name/model
    additional_context: str             # Extra context string
    similar_cases: List[Dict[str, Any]] # Historical similar cases

    # Extra metadata for conflict detection
    structured_metadata: Dict[str, Any]
    policy_path: Optional[str]           # Path to policy document for detection

    # ── Invocation flags ─────────────────────────────────────────────────────
    severity_invoked: bool
    occurrence_invoked: bool
    detection_invoked: bool

    # ── Scores written by each node ──────────────────────────────────────────
    scores_valid: bool
    severity_score: Optional[int]
    occurrence_score: Optional[int]
    detection_score: Optional[int]

    # ── RPN ──────────────────────────────────────────────────────────────────
    rpn_computed: bool
    rpn_value: Optional[int]

    # ── Control flags ─────────────────────────────────────────────────────────
    conflict_detected: bool
    escalation_required: bool
    escalation_reason: str
    workflow_status: Optional[Literal["completed", "escalated", "halted"]]

    # ── Internal audit ────────────────────────────────────────────────────────
    retry_counts: Annotated[Dict[str, int], merge_dicts]        # {"severity": 0, "occurrence": 0, "detection": 0}
    errors: Annotated[List[str], operator.add]
    agent_outputs: Annotated[Dict[str, Any], merge_dicts]       # Full raw outputs stored for audit
