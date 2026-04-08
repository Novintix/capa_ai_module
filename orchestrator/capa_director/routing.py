from .state import DirectorState

# RPN threshold — below this, RCA is skipped and we go straight to action plan
LOW_RISK_RPN = 100


def route_after_risk(state: DirectorState) -> str:
    """
    After Risk Analysis (O2):
    Always route to human_review_risk so the human can see the results
    before anything else runs — regardless of RPN score.
    """
    if state.get("error"):
        return "error_recovery"

    print("\n[ROUTER] Risk Analysis done → human_review_risk (always)")
    return "human_review_risk"


def route_after_human_review_risk(state: DirectorState) -> str:
    """
    After the human reviews the Risk Analysis output:
    - Rejected          → error_recovery
    - Approved + RPN>=100 → rca
    - Approved + RPN<100  → action_plan (skip RCA for low-risk)
    """
    if state.get("error"):
        return "error_recovery"

    if state.get("human_approved") is False:
        return "error_recovery"

    # Determine next step based on RPN
    risk_output  = state.get("risk_analysis_output") or {}
    final_report = risk_output.get("final_report") or {}
    rpn_data     = final_report.get("rpn") or {}
    raw_rpn      = rpn_data.get("rpn_value")
    rpn_level    = rpn_data.get("rpn_level", "UNKNOWN")

    try:
        rpn_score = float(raw_rpn) if raw_rpn is not None else 0.0
    except (TypeError, ValueError):
        rpn_score = 0.0

    # If RPN is missing/unparseable, default to running RCA (safer)
    if rpn_score == 0.0 and raw_rpn is None:
        print("[ROUTER] RPN not found → defaulting to rca")
        return "rca"

    if rpn_score < LOW_RISK_RPN:
        print(f"[ROUTER] RPN {rpn_score} ({rpn_level}) < {LOW_RISK_RPN} → action_plan (RCA skipped)")
        return "action_plan"

    print(f"[ROUTER] RPN {rpn_score} ({rpn_level}) >= {LOW_RISK_RPN} → rca")
    return "rca"


def route_after_rca(state: DirectorState) -> str:
    """
    After RCA (O3):
    - Error                     → error_recovery
    - Root cause identified     → action_plan
    - No root cause found       → error_recovery (will retry or escalate)
    """
    if state.get("error"):
        return "error_recovery"

    rca_output = state.get("rca_output") or {}

    # Check if a valid root cause was identified
    root_cause = rca_output.get("root_cause")
    if not root_cause or not root_cause.get("cause_text"):
        print("[ROUTER] RCA: No root cause identified → error_recovery")
        return "error_recovery"

    print(f"[ROUTER] RCA: Root cause found ({rca_output.get('confidence', 'UNKNOWN')} confidence) → action_plan")
    return "action_plan"


def route_after_action_plan(state: DirectorState) -> str:
    """
    After Action Plan (A15):
    - Error                  → error_recovery
    - No action items        → error_recovery
    - Actions present        → effectiveness
    """
    if state.get("error"):
        return "error_recovery"

    plan_output = state.get("action_plan_output") or {}
    action_items = plan_output.get("action_items", [])

    if not action_items:
        print("[ROUTER] Action Plan: No action items generated → error_recovery")
        return "error_recovery"

    print(f"[ROUTER] Action Plan: {len(action_items)} actions generated → effectiveness")
    return "effectiveness"


def route_after_effectiveness(state: DirectorState) -> str:
    """
    After Effectiveness Evaluation (A16):
    - Error      → error_recovery
    - Otherwise  → finalize
    """
    if state.get("error"):
        return "error_recovery"

    print("[ROUTER] Effectiveness complete → finalize")
    return "finalize"