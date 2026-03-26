import time
from typing import Dict, Any
from .state import DirectorState

# ── Sub-orchestrator / agent imports ─────────────────────────────────────────
from orchestrator.risk_analysis_orchestrator_service.orchestrator import orchestrator_graph as risk_graph
from orchestrator.rca_v2.agent_integrated import RCAOrchestratorV2Integrated
from Agents.action_plan.graph import build_graph as build_action_graph
from Agents.effectiveness.graph import build_graph as build_effectiveness_graph

from orchestrator.rca_v2.schemas import WhyAnalysisInput
from Agents.action_plan.model import CapaInput
from Agents.effectiveness.model import EffectivenessEvaluationInput, ActionItemInput


# ── Helper ────────────────────────────────────────────────────────────────────

def _thread_id(state: DirectorState, suffix: str) -> str:
    return f"director-{suffix}-{state['complaint_id']}-{int(time.time())}"


# ── Pipeline nodes ────────────────────────────────────────────────────────────

def risk_analysis_node(state: DirectorState) -> dict:
    print("\n[DIRECTOR] ── Risk Analysis (O2) ──────────────────────────────")

    risk_input = {
        "raw_input": state["complaint"],
        "agent_results": [],
        "node_log": [],
        "errors": [],
        "correction_count": 0,
    }
    config = {"configurable": {"thread_id": _thread_id(state, "risk")}}

    try:
        result = risk_graph.invoke(risk_input, config=config)
    except Exception as exc:
        return {
            "error": f"Risk Analysis exception: {exc}",
            "failed_node": "risk_analysis",
            "status": "error",
        }

    if result.get("status") == "awaiting_correction" or result.get("validation_passed") is False:
        error_msg = result.get("validation_error", "Risk Analysis failed validation.")
        return {
            "error": f"Risk Analysis Error: {error_msg}",
            "failed_node": "risk_analysis",
            "status": "error",
        }

    print("[DIRECTOR] Risk Analysis completed ✓")
    return {
        "risk_analysis_output": result,
        "status": "running",
        "error": None,
        "failed_node": None,
    }


def rca_node(state: DirectorState) -> dict:
    print("\n[DIRECTOR] ── RCA v2 (O3) ─────────────────────────────────────")

    # Human-in-the-loop gate: if human rejected, abort
    if state.get("human_approved") is False:
        return {
            "error": f"Human reviewer rejected RCA step. Feedback: {state.get('human_feedback', 'No feedback provided')}",
            "failed_node": "rca",
            "status": "error",
        }

    orchestrator = RCAOrchestratorV2Integrated()

    rca_input = WhyAnalysisInput(
        complaint_id=state["complaint_id"],
        complaint=state["complaint"],
        evidence=state.get("evidence") or "",
        sop=state.get("sop") or "",
        fmea_document_path=state.get("fmea_document_path"),
        max_depth=state["max_rca_depth"],
    )

    try:
        result = orchestrator.analyze(rca_input)
    except Exception as exc:
        return {
            "error": f"RCA exception: {exc}",
            "failed_node": "rca",
            "status": "error",
        }

    if result.get("error") and not result.get("root_cause"):
        return {
            "error": f"RCA Error: {result['error']}",
            "failed_node": "rca",
            "status": "error",
        }

    print("[DIRECTOR] RCA completed ✓")
    return {
        "rca_output": result,
        "status": "running",
        "error": None,
        "failed_node": None,
        "human_approved": None,   # Reset for next human gate
    }


def action_plan_node(state: DirectorState) -> dict:
    print("\n[DIRECTOR] ── Action Planner (A15) ────────────────────────────")

    # Human-in-the-loop gate
    if state.get("human_approved") is False:
        return {
            "error": f"Human reviewer rejected Action Plan step. Feedback: {state.get('human_feedback', 'No feedback')}",
            "failed_node": "action_plan",
            "status": "error",
        }

    rca  = state.get("rca_output") or {}
    risk = state.get("risk_analysis_output") or {}

    root_cause     = rca.get("root_cause") or {}
    why_iterations = rca.get("why_iterations", [])

    why_text = "\n".join([
        f"Why {i['depth']}: {i['question']} -> "
        f"{i['selected_cause']['cause_text'] if i.get('selected_cause') else 'N/A'}"
        for i in why_iterations
    ])

    final_report   = risk.get("final_report") or {}
    severity_label = final_report.get("rpn", {}).get("severity_label", "MODERATE")

    capa_input = CapaInput(
        investigation_summary=(
            f"Analysis of {state['complaint']}. Evidence: {state.get('evidence', '')}"
        ),
        containment_actions=state["containment_actions"],
        five_why_analysis=why_text or "RCA skipped (low risk)",
        primary_root_cause=root_cause.get("cause_text", "Unknown"),
        evidence_collected=state.get("evidence") or "Risk Analysis Evidence",
        root_cause_verification_status=(
            "Verified" if rca.get("confidence") == "HIGH" else "Pending"
        ),
        severity_level=severity_label,
        timeline_constraint=state["timeline_constraint"],
        available_resources=state["available_resources"],
    )

    try:
        graph  = build_action_graph()
        result = graph.invoke({"capa_input": capa_input})
    except Exception as exc:
        return {
            "error": f"Action Plan exception: {exc}",
            "failed_node": "action_plan",
            "status": "error",
        }

    print("[DIRECTOR] Action Plan completed ✓")
    return {
        "action_plan_output": result,
        "status": "running",
        "error": None,
        "failed_node": None,
        "human_approved": None,
    }


def effectiveness_node(state: DirectorState) -> dict:
    print("\n[DIRECTOR] ── Effectiveness (A16) ─────────────────────────────")

    rca  = state.get("rca_output") or {}
    plan = state.get("action_plan_output") or {}

    root_cause_text = rca.get("root_cause", {}).get("cause_text", "Unknown")
    action_items    = plan.get("action_items", [])

    eff_actions = [
        ActionItemInput(
            action_id=f"ACT-{i+1:02d}",
            action_description=f"{item['action_type']}: {item['action_description']}",
        )
        for i, item in enumerate(action_items)
    ]

    eff_input = EffectivenessEvaluationInput(
        root_cause_description=root_cause_text,
        actions=eff_actions,
        system_context=state["system_context"],
        supporting_evidence=state.get("evidence") or "",
    )

    try:
        graph  = build_effectiveness_graph()
        result = graph.invoke({"evaluation_input": eff_input})
    except Exception as exc:
        return {
            "error": f"Effectiveness exception: {exc}",
            "failed_node": "effectiveness",
            "status": "error",
        }

    print("[DIRECTOR] Effectiveness completed ✓")
    return {
        "effectiveness_output": result,
        "status": "running",
        "error": None,
        "failed_node": None,
    }


def finalize_node(state: DirectorState) -> dict:
    print("\n[DIRECTOR] ── Finalizing ───────────────────────────────────────")

    if state.get("error"):
        print(f"[DIRECTOR] Completed with error: {state['error']}")
        return {"status": "error"}

    print("[DIRECTOR] CAPA Analysis complete ✓")
    return {"status": "completed"}


# ── Error recovery node ───────────────────────────────────────────────────────

def error_recovery_node(state: DirectorState) -> dict:
    """
    Intelligent error recovery:
    - Increments retry counter
    - Decides whether to retry the failed node or give up
    - Sets recovery_next so the conditional edge knows where to go
    """
    retry_count = (state.get("retry_count") or 0) + 1
    max_retries = state.get("max_retries") or 2
    failed_node = state.get("failed_node", "unknown")
    error       = state.get("error", "Unknown error")

    print(f"\n[RECOVERY] Node '{failed_node}' failed (attempt {retry_count}/{max_retries})")
    print(f"[RECOVERY] Error: {error}")

    if retry_count <= max_retries:
        print(f"[RECOVERY] Retrying '{failed_node}'...")
        return {
            "retry_count": retry_count,
            "error": None,                # Clear error to allow retry
            "recovery_next": failed_node, # Route back to the failed node
            "status": "running",
        }
    else:
        print(f"[RECOVERY] Max retries reached for '{failed_node}'. Escalating to finalize.")
        return {
            "retry_count": retry_count,
            "error": f"[UNRECOVERABLE] {failed_node} failed after {max_retries} retries: {error}",
            "recovery_next": "finalize",
            "status": "error",
        }