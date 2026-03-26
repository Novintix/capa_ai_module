from .state import DirectorState

# ── RPN thresholds ────────────────────────────────────────────────────────────
HIGH_RISK_RPN = 200      # Above this → mandatory full RCA
LOW_RISK_RPN  = 100      # Below this → skip RCA, go straight to action plan


def route_after_risk(state: DirectorState) -> str:
    """
    After Risk Analysis (O2):
    - Error           → error_recovery
    - RPN > 200       → rca  (high risk, full investigation)
    - RPN 100–200     → rca  (moderate, still needs RCA)
    - RPN < 100       → action_plan (low risk, skip RCA)
    """
    if state.get("error"):
        return "error_recovery"

    risk_output = state.get("risk_analysis_output") or {}
    final_report = risk_output.get("final_report") or {}
    rpn_score = final_report.get("rpn", {}).get("score", 0)

    print(f"\n[ROUTER] RPN Score: {rpn_score}")

    if rpn_score >= LOW_RISK_RPN:
        print("[ROUTER] High/Moderate risk → routing to RCA")
        return "rca"
    else:
        print("[ROUTER] Low risk → skipping RCA, routing to Action Plan")
        return "action_plan"


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