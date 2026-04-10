"""
Criticality Ranking Tool for Zero Evidence Agent

Computes a composite criticality score for each cause using:

    score = (0.35 * severity)
           + (0.20 * single_point_failure_score)
           + (0.20 * system_dependency_score)
           + (0.15 * safety_impact_score)
           + (0.10 * safety_blocking_score)

Where:
  single_point_failure_score  : 10 if single point failure, else 5
  system_dependency_score     : 10 if process step directly produces the
                                 feature named in the complaint, else 5
  safety_impact_score         : 10 if safety_risk == "high"
                                 6 if safety_risk == "medium"
                                 2 if safety_risk == "low"
  safety_blocking_score       : 10 if system disables itself for safety
                                 5 if partial blocking/warning
                                 0 if no safety blocking

This tool does NOT call the LLM. It only performs deterministic math.
LLM evaluations are passed in as input.
"""

from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Safety impact mapping
# ---------------------------------------------------------------------------

_SAFETY_SCORE_MAP = {
    "high": 10,
    "medium": 6,
    "low": 2
}

# Safety blocking threshold mapping
_SAFETY_BLOCKING_MAP = {
    "full": 10,      # System completely disables itself
    "partial": 5,    # System shows warnings or partial blocking
    "none": 0        # No safety blocking mechanism
}


def _get_system_dependency_score(process_step: str, question: str) -> int:
    """
    Determine whether the process step directly produces the feature
    referenced in the original question.

    Heuristic: check if any keyword from the process_step appears in the question.
    Score 10 if there is keyword overlap, else 5.

    Args:
        process_step: Process step of the cause.
        question:     Original why question.

    Returns:
        10 or 5
    """
    step_keywords = set(process_step.lower().split())
    question_lower = question.lower()

    for keyword in step_keywords:
        if len(keyword) >= 4 and keyword in question_lower:
            return 10

    return 5


def compute_criticality_scores(
    causes: List[Dict[str, Any]],
    llm_evaluations: List[Dict[str, Any]],
    question: str
) -> List[Dict[str, Any]]:
    """
    Compute composite criticality score for each cause.

    Args:
        causes:           Raw cause list from input (with severity, process_step, etc.)
        llm_evaluations:  LLM output — list of dicts with cause_id, single_point_failure,
                          safety_risk, safety_blocking, reason
        question:         Original question (used for system dependency check)

    Returns:
        List of causes enriched with:
          - single_point_failure_score
          - system_dependency_score
          - safety_impact_score
          - safety_blocking_score
          - final_score
          - llm_reason
    """

    # Build a lookup map from llm_evaluations by cause_id
    llm_map: Dict[str, Dict[str, Any]] = {}
    for evaluation in llm_evaluations:
        cause_id = evaluation.get("cause_id")
        if cause_id:
            llm_map[cause_id] = evaluation

    scored = []

    for cause in causes:
        cause_id = cause.get("cause_id", "")
        severity = cause.get("severity", 5) or 5  # Default 5 if None

        # Retrieve LLM evaluation for this cause
        llm_eval = llm_map.get(cause_id, {})

        # Single point failure score
        spf = llm_eval.get("single_point_failure", False)
        single_point_failure_score = 10 if spf else 5

        # System dependency score
        process_step = cause.get("process_step", "")
        system_dependency_score = _get_system_dependency_score(process_step, question)

        # Safety impact score
        safety_risk = str(llm_eval.get("safety_risk", "low")).lower()
        safety_impact_score = _SAFETY_SCORE_MAP.get(safety_risk, 2)

        # Safety blocking score (new factor)
        safety_blocking = str(llm_eval.get("safety_blocking", "none")).lower()
        safety_blocking_score = _SAFETY_BLOCKING_MAP.get(safety_blocking, 0)

        # Composite score with adjusted weights (total = 1.0)
        final_score = (
            (0.35 * severity)                           # Severity: 35%
            + (0.20 * single_point_failure_score)       # Single-point failure: 20%
            + (0.20 * system_dependency_score)          # System dependency: 20%
            + (0.15 * safety_impact_score)              # Safety impact: 15%
            + (0.10 * safety_blocking_score)            # Safety blocking: 10%
        )

        scored.append({
            "cause_id": cause_id,
            "cause_text": cause.get("cause_text", ""),
            "process_step": process_step,
            "failure_mode": cause.get("failure_mode", ""),
            "potential_effects": cause.get("potential_effects", ""),
            "severity": severity,
            "single_point_failure": spf,
            "single_point_failure_score": single_point_failure_score,
            "system_dependency_score": system_dependency_score,
            "safety_risk": safety_risk,
            "safety_impact_score": safety_impact_score,
            "safety_blocking": safety_blocking,
            "safety_blocking_score": safety_blocking_score,
            "final_score": round(final_score, 4),
            "llm_reason": llm_eval.get("reason", "No LLM evaluation available")
        })

    # Sort descending by final_score
    scored.sort(key=lambda x: x["final_score"], reverse=True)

    return scored


def select_top_cause(scored_causes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Select the single most critical cause from the scored list.

    Guardrail: if the top cause has a severity difference > 2 from
    the second-best cause (raw severity), severity takes absolute priority.

    Args:
        scored_causes: Sorted list from compute_criticality_scores() (highest first)

    Returns:
        The single selected cause dict
    """
    if not scored_causes:
        raise ValueError("No scored causes available for selection")

    if len(scored_causes) == 1:
        return scored_causes[0]

    top = scored_causes[0]
    second = scored_causes[1]

    # Guardrail: if severity difference > 2, re-rank by raw severity alone
    top_severity = top.get("severity", 0)
    second_severity = second.get("severity", 0)

    if abs(top_severity - second_severity) > 2:
        # Re-select strictly by severity
        by_severity = sorted(scored_causes, key=lambda x: x.get("severity", 0), reverse=True)
        return by_severity[0]

    return top
