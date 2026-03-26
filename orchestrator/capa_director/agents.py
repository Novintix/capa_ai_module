import time
from .state import DirectorState

# ── Sub-orchestrator / agent imports (UNCHANGED) ─────────────────────────────
from orchestrator.risk_analysis_orchestrator_service.orchestrator import orchestrator_graph as risk_graph
from orchestrator.rca_v2.agent_integrated import RCAOrchestratorV2Integrated
from Agents.action_plan.graph import build_graph as build_action_graph
from Agents.effectiveness.graph import build_graph as build_effectiveness_graph

from orchestrator.rca_v2.schemas import WhyAnalysisInput
from Agents.action_plan.model import CapaInput
from Agents.effectiveness.model import EffectivenessEvaluationInput, ActionItemInput


def _ts(state: DirectorState, tag: str) -> str:
    return f"director-{tag}-{state['complaint_id']}-{int(time.time())}"


# ── Agent nodes ───────────────────────────────────────────────────────────────
# These are IDENTICAL to before — only error returns are cleaner.
# O1 Director controls them; they don't know about each other.

def risk_analysis_node(state: DirectorState) -> dict:
    print("\n[O2 RISK] Running Risk Analysis...")

    risk_input = {
        "raw_input":       state["complaint"],
        "agent_results":   [],
        "node_log":        [],
        "errors":          [],
        "correction_count": 0,
    }
    config = {"configurable": {"thread_id": _ts(state, "risk")}}

    try:
        result = risk_graph.invoke(risk_input, config=config)
    except Exception as exc:
        return {"error": f"Risk Analysis exception: {exc}", "status": "error"}

    if result.get("status") == "awaiting_correction" or result.get("validation_passed") is False:
        return {
            "error":  result.get("validation_error", "Risk Analysis failed validation."),
            "status": "error",
        }

    print("[O2 RISK] Done ✓")
    return {"risk_analysis_output": result, "error": None}


def rca_node(state: DirectorState) -> dict:
    """
    O1 Director passes rca_mode ("standard" | "deep").
    Deep mode uses max depth and requires FMEA.
    Standard mode uses configured depth.
    Agent internals are UNCHANGED — only input parameters differ.
    """
    rca_mode  = state.get("rca_mode", "standard")
    max_depth = state["max_rca_depth"] if rca_mode == "standard" else 7

    print(f"\n[O3 RCA] Running RCA in '{rca_mode}' mode (max_depth={max_depth})...")

    # Human gate — check if reviewer rejected this step
    if state.get("human_approved") is False:
        return {
            "error":  f"Human rejected RCA. Feedback: {state.get('human_feedback', 'none')}",
            "status": "error",
        }

    orchestrator = RCAOrchestratorV2Integrated()

    rca_input = WhyAnalysisInput(
        complaint_id       = state["complaint_id"],
        complaint          = state["complaint"],
        evidence           = state.get("evidence") or "",
        sop                = state.get("sop") or "",
        fmea_document_path = state.get("fmea_document_path"),   # Used in deep mode
        max_depth          = max_depth,
    )

    try:
        result = orchestrator.analyze(rca_input)
    except Exception as exc:
        return {"error": f"RCA exception: {exc}", "status": "error"}

    if result.get("error") and not result.get("root_cause"):
        return {"error": f"RCA Error: {result['error']}", "status": "error"}

    print(f"[O3 RCA] Done ✓ confidence={result.get('confidence')}")
    return {
        "rca_output":    result,
        "human_approved": None,   # Reset for next human gate
        "error":         None,
    }


def action_plan_node(state: DirectorState) -> dict:
    print("\n[A15 ACTION PLAN] Building Action Plan...")

    # Human gate
    if state.get("human_approved") is False:
        return {
            "error":  f"Human rejected Action Plan. Feedback: {state.get('human_feedback', 'none')}",
            "status": "error",
        }

    rca  = state.get("rca_output") or {}
    risk = state.get("risk_analysis_output") or {}

    root_cause     = rca.get("root_cause") or {}
    why_iterations = rca.get("why_iterations", [])
    plan_retries   = state.get("plan_retry_count", 0)

    why_text = "\n".join([
        f"Why {i['depth']}: {i['question']} -> "
        f"{i['selected_cause']['cause_text'] if i.get('selected_cause') else 'N/A'}"
        for i in why_iterations
    ]) or "RCA skipped (low risk)"

    final_report   = risk.get("final_report") or {}
    severity_label = final_report.get("rpn", {}).get("severity_label", "MODERATE")

    # On retry, O1 signals higher scope via plan_retry_count
    scope_note = (
        f" [Retry {plan_retries}: expand scope, add more corrective actions]"
        if plan_retries > 0 else ""
    )

    capa_input = CapaInput(
        investigation_summary     = f"Analysis of {state['complaint']}. Evidence: {state.get('evidence', '')}{scope_note}",
        containment_actions       = state["containment_actions"],
        five_why_analysis         = why_text,
        primary_root_cause        = root_cause.get("cause_text", "Unknown"),
        evidence_collected        = state.get("evidence") or "Risk Analysis Evidence",
        root_cause_verification_status = "Verified" if rca.get("confidence") == "HIGH" else "Pending",
        severity_level            = severity_label,
        timeline_constraint       = state["timeline_constraint"],
        available_resources       = state["available_resources"],
    )

    try:
        graph  = build_action_graph()
        result = graph.invoke({"capa_input": capa_input})
    except Exception as exc:
        return {"error": f"Action Plan exception: {exc}", "status": "error"}

    print(f"[A15 ACTION PLAN] Done ✓ actions={len(result.get('action_items', []))}")
    return {
        "action_plan_output": result,
        "human_approved":     None,
        "error":              None,
    }


def effectiveness_node(state: DirectorState) -> dict:
    print("\n[A16 EFFECTIVENESS] Evaluating effectiveness...")

    # Human-in-the-loop gate — check if reviewer rejected this step
    if state.get("human_approved") is False:
        return {
            "error":  f"Human rejected Effectiveness Evaluation. Feedback: {state.get('human_feedback', 'none')}",
            "status": "error",
        }

    rca  = state.get("rca_output") or {}
    plan = state.get("action_plan_output") or {}

    root_cause_text = rca.get("root_cause", {}).get("cause_text", "Unknown")
    action_items    = plan.get("action_items", [])

    eff_actions = [
        ActionItemInput(
            action_id          = f"ACT-{i+1:02d}",
            action_description = f"{item['action_type']}: {item['action_description']}",
        )
        for i, item in enumerate(action_items)
    ]

    eff_input = EffectivenessEvaluationInput(
        root_cause_description = root_cause_text,
        actions                = eff_actions,
        system_context         = state["system_context"],
        supporting_evidence    = state.get("evidence") or "",
    )

    try:
        graph  = build_effectiveness_graph()
        result = graph.invoke({"evaluation_input": eff_input})
    except Exception as exc:
        return {"error": f"Effectiveness exception: {exc}", "status": "error"}

    print(f"[A16 EFFECTIVENESS] Done ✓ score={result.get('overall_score')}%")
    return {"effectiveness_output": result, "error": None}