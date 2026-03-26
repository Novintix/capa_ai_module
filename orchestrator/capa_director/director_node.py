from .state import DirectorState

# ── Quality thresholds — tune these without touching any agent ────────────────
RPN_CRITICAL      = 200   # Above → deep RCA (max depth, FMEA required)
RPN_MODERATE      = 100   # Above → standard RCA
RPN_LOW           = 100   # Below → skip RCA entirely

RCA_CONFIDENCE_OK = ["HIGH", "MEDIUM"]   # Acceptable RCA confidence levels
MIN_WHY_DEPTH     = 3                    # Minimum why iterations expected
MAX_RCA_RETRIES   = 2                    # O1 will re-run RCA at most twice

MIN_ACTION_ITEMS  = 3                    # Minimum acceptable actions
MAX_PLAN_RETRIES  = 1                    # O1 will re-run Action Plan at most once

EFFECTIVENESS_PASS_SCORE = 60            # Minimum effectiveness % to finalize


def director_node(state: DirectorState) -> dict:
    """
    O1 Director — the thinking node.

    Called after EVERY agent finishes.
    Reads outputs, applies quality gates, decides next_agent.
    Never touches agent internals — only reads their outputs.
    """

    print("\n" + "="*60)
    print("[O1 DIRECTOR] Assessing situation...")

    risk = state.get("risk_analysis_output")
    rca  = state.get("rca_output")
    plan = state.get("action_plan_output")
    eff  = state.get("effectiveness_output")

    rca_retries  = state.get("rca_retry_count", 0)
    plan_retries = state.get("plan_retry_count", 0)

    # ── GATE 1: Nothing done yet — start with Risk Analysis ──────────────────
    if not risk:
        reasoning = "No outputs yet. Starting with Risk Analysis (O2) to assess complaint severity."
        print(f"[O1 DIRECTOR] → risk_analysis | {reasoning}")
        return {
            "next_agent":         "risk_analysis",
            "director_reasoning": reasoning,
            "status":             "running",
        }

    # ── GATE 2: Risk done — decide whether RCA is needed and at what depth ───
    if risk and not rca:
        final_report = risk.get("final_report") or {}
        rpn_data     = final_report.get("rpn") or {}
        rpn_score    = rpn_data.get("score", 0)
        severity     = rpn_data.get("severity_label", "UNKNOWN")

        print(f"[O1 DIRECTOR] Risk Analysis result: RPN={rpn_score}, Severity={severity}")

        if rpn_score >= RPN_CRITICAL:
            reasoning = (
                f"RPN {rpn_score} is CRITICAL (≥{RPN_CRITICAL}). "
                f"Deploying deep RCA with FMEA analysis and max depth."
            )
            print(f"[O1 DIRECTOR] → rca (deep) | {reasoning}")
            return {
                "next_agent":         "rca",
                "rca_mode":           "deep",
                "director_reasoning": reasoning,
                "status":             "running",
            }

        elif rpn_score >= RPN_MODERATE:
            reasoning = (
                f"RPN {rpn_score} is MODERATE ({RPN_MODERATE}–{RPN_CRITICAL}). "
                f"Standard RCA sufficient."
            )
            print(f"[O1 DIRECTOR] → rca (standard) | {reasoning}")
            return {
                "next_agent":         "rca",
                "rca_mode":           "standard",
                "director_reasoning": reasoning,
                "status":             "running",
            }

        else:
            reasoning = (
                f"RPN {rpn_score} is LOW (<{RPN_LOW}). "
                f"Skipping RCA. Proceeding directly to Action Plan."
            )
            print(f"[O1 DIRECTOR] → action_plan (RCA skipped) | {reasoning}")
            return {
                "next_agent":         "action_plan",
                "director_reasoning": reasoning,
                "status":             "running",
            }

    # ── GATE 3: RCA done — evaluate quality ──────────────────────────────────
    if rca and not plan:
        confidence     = rca.get("confidence", "UNKNOWN")
        root_cause     = rca.get("root_cause") or {}
        why_iterations = rca.get("why_iterations", [])
        why_depth      = len(why_iterations)

        print(f"[O1 DIRECTOR] RCA result: confidence={confidence}, why_depth={why_depth}, retries={rca_retries}")

        # Quality gate: acceptable confidence AND sufficient depth
        confidence_ok = confidence in RCA_CONFIDENCE_OK
        depth_ok      = why_depth >= MIN_WHY_DEPTH
        has_cause     = bool(root_cause.get("cause_text"))

        if confidence_ok and depth_ok and has_cause:
            reasoning = (
                f"RCA acceptable — confidence={confidence}, "
                f"why_depth={why_depth}, root cause identified. "
                f"Proceeding to Action Plan."
            )
            print(f"[O1 DIRECTOR] → action_plan | {reasoning}")
            return {
                "next_agent":         "action_plan",
                "director_reasoning": reasoning,
                "status":             "running",
            }

        # Quality gate failed — can we retry?
        if rca_retries < MAX_RCA_RETRIES:
            # Escalate mode on retry
            new_mode = "deep" if state.get("rca_mode") != "deep" else "deep"
            issues   = []
            if not confidence_ok: issues.append(f"confidence={confidence}")
            if not depth_ok:      issues.append(f"why_depth={why_depth}<{MIN_WHY_DEPTH}")
            if not has_cause:     issues.append("no root cause identified")

            reasoning = (
                f"RCA quality insufficient ({', '.join(issues)}). "
                f"Retrying in '{new_mode}' mode (attempt {rca_retries + 1}/{MAX_RCA_RETRIES})."
            )
            print(f"[O1 DIRECTOR] → rca (retry) | {reasoning}")
            return {
                "next_agent":         "rca",
                "rca_mode":           new_mode,
                "rca_retry_count":    rca_retries + 1,
                "rca_output":         None,          # Clear previous RCA output
                "director_reasoning": reasoning,
                "status":             "running",
            }

        # Max retries hit — proceed anyway with warning
        reasoning = (
            f"RCA quality still insufficient after {rca_retries} retries "
            f"(confidence={confidence}). Proceeding to Action Plan with best available result."
        )
        print(f"[O1 DIRECTOR] → action_plan (RCA exhausted) | {reasoning}")
        return {
            "next_agent":         "action_plan",
            "director_reasoning": reasoning,
            "status":             "running",
        }

    # ── GATE 4: Action Plan done — evaluate quality ───────────────────────────
    if plan and not eff:
        action_items = plan.get("action_items", [])
        item_count   = len(action_items)

        print(f"[O1 DIRECTOR] Action Plan result: {item_count} actions, retries={plan_retries}")

        if item_count >= MIN_ACTION_ITEMS:
            reasoning = (
                f"Action Plan acceptable — {item_count} actions generated "
                f"(minimum {MIN_ACTION_ITEMS}). Proceeding to Effectiveness Evaluation."
            )
            print(f"[O1 DIRECTOR] → effectiveness | {reasoning}")
            return {
                "next_agent":         "effectiveness",
                "director_reasoning": reasoning,
                "status":             "running",
            }

        # Too few actions — retry if allowed
        if plan_retries < MAX_PLAN_RETRIES:
            reasoning = (
                f"Action Plan too weak — only {item_count} actions "
                f"(minimum {MIN_ACTION_ITEMS}). "
                f"Regenerating with higher scope (attempt {plan_retries + 1}/{MAX_PLAN_RETRIES})."
            )
            print(f"[O1 DIRECTOR] → action_plan (retry) | {reasoning}")
            return {
                "next_agent":          "action_plan",
                "plan_retry_count":    plan_retries + 1,
                "action_plan_output":  None,           # Clear to regenerate
                "director_reasoning":  reasoning,
                "status":              "running",
            }

        # Proceed with what we have
        reasoning = (
            f"Action Plan has only {item_count} actions after {plan_retries} retries. "
            f"Proceeding to Effectiveness with available plan."
        )
        print(f"[O1 DIRECTOR] → effectiveness (plan exhausted) | {reasoning}")
        return {
            "next_agent":         "effectiveness",
            "director_reasoning": reasoning,
            "status":             "running",
        }

    # ── GATE 5: Effectiveness done — final quality check ─────────────────────
    if eff:
        overall_score = eff.get("overall_score", 0)

        print(f"[O1 DIRECTOR] Effectiveness result: score={overall_score}%, retries={plan_retries}")

        if overall_score >= EFFECTIVENESS_PASS_SCORE:
            reasoning = (
                f"Effectiveness score {overall_score}% passes threshold "
                f"({EFFECTIVENESS_PASS_SCORE}%). Analysis complete."
            )
            print(f"[O1 DIRECTOR] → END | {reasoning}")
            return {
                "next_agent":         "END",
                "director_reasoning": reasoning,
                "status":             "completed",
            }

        # Score too low — regenerate action plan if retries left
        if plan_retries < MAX_PLAN_RETRIES:
            reasoning = (
                f"Effectiveness score {overall_score}% is below threshold "
                f"({EFFECTIVENESS_PASS_SCORE}%). "
                f"Looping back to regenerate Action Plan "
                f"(attempt {plan_retries + 1}/{MAX_PLAN_RETRIES})."
            )
            print(f"[O1 DIRECTOR] → action_plan (effectiveness too low) | {reasoning}")
            return {
                "next_agent":          "action_plan",
                "plan_retry_count":    plan_retries + 1,
                "action_plan_output":  None,
                "effectiveness_output": None,
                "director_reasoning":  reasoning,
                "status":              "running",
            }

        # Accept result — can't improve further
        reasoning = (
            f"Effectiveness score {overall_score}% below threshold but "
            f"max retries reached. Finalizing with current results."
        )
        print(f"[O1 DIRECTOR] → END (accepted) | {reasoning}")
        return {
            "next_agent":         "END",
            "director_reasoning": reasoning,
            "status":             "completed",
        }

    # ── Fallback (should never reach here) ───────────────────────────────────
    return {
        "next_agent":         "END",
        "director_reasoning": "Unexpected state — finalizing.",
        "status":             "error",
        "error":              "Director reached unexpected state.",
    }