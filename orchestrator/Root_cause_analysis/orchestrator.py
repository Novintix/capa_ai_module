"""
Root Cause Analysis Orchestrator (LangGraph).

Flow:
    START
      └─► initialize_node
            ├─► (fishbone) → run_fishbone_node
            │                  └─► await_category_selection_node
            │                        ├─► END  ← HITL #2 pause (user picks category)
            │                        └─► run_why_node
            │                              └─► await_action_plan_node
            │                                    ├─► END  ← HITL #3 pause (user confirms)
            │                                    └─► finalize_node → END
            └─► (why) → run_why_node
                          └─► await_action_plan_node
                                ├─► END  ← HITL #3 pause
                                └─► finalize_node → END

HITL Resume:
  HITL #2: graph.invoke({"selected_category": "..."}, config)
  HITL #3: graph.invoke({"action_plan_confirmed": True|False}, config)
"""

from __future__ import annotations

import datetime
import os
import time
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.redis import RedisSaver

from orchestrator.fishbone_v3.agent import FishboneOrchestratorV3
from orchestrator.fishbone_v3.session_memory import SessionMemoryManagerV3 as FishboneSessionManager
from orchestrator.fishbone_v3.schemas import FishboneV3Input
from orchestrator.why_analysis_v3.agent import WhyAnalysisV3Orchestrator
from orchestrator.why_analysis_v3.schemas import WhyAnalysisV3Input

from .logger import log_error, log_info, log_transition
from .state import RCAGraphState

try:
    from config.redis_config import REDIS_URL as _REDIS_URL
except Exception:
    _REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── Constants from environment ────────────────────────────────────────────────
ACTION_PLAN_ENDPOINT = os.getenv("RCA_ACTION_PLAN_ENDPOINT", "/action_plan")

# ══════════════════════════════════════════════════════════════════════════════
# AGENT SINGLETONS
# ══════════════════════════════════════════════════════════════════════════════

_fishbone_orchestrator: Optional[FishboneOrchestratorV3] = None
_why_orchestrator: Optional[WhyAnalysisV3Orchestrator] = None
_fishbone_session_manager: Optional[FishboneSessionManager] = None


def _get_fishbone_orchestrator() -> FishboneOrchestratorV3:
    global _fishbone_orchestrator
    if _fishbone_orchestrator is None:
        _fishbone_orchestrator = FishboneOrchestratorV3()
    return _fishbone_orchestrator


def _get_why_orchestrator() -> WhyAnalysisV3Orchestrator:
    global _why_orchestrator
    if _why_orchestrator is None:
        _why_orchestrator = WhyAnalysisV3Orchestrator()
    return _why_orchestrator


def _get_fishbone_session_manager() -> Optional[FishboneSessionManager]:
    global _fishbone_session_manager
    if _fishbone_session_manager is None:
        try:
            _fishbone_session_manager = FishboneSessionManager(redis_url=_REDIS_URL)
        except Exception as exc:
            log_error("get_fishbone_session_manager", str(exc))
    return _fishbone_session_manager


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def deep_serialize(obj: Any) -> Any:
    """Recursively convert any object to a JSON-serializable form."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return deep_serialize(obj.model_dump(mode="json"))
        except Exception:
            try:
                return deep_serialize(obj.model_dump())
            except Exception:
                return str(obj)
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return deep_serialize(obj.dict())
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [deep_serialize(v) for v in obj]
    return obj


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _category_from_cause(cause: Any) -> str:
    if isinstance(cause, dict):
        return str(cause.get("category", "")).strip()
    if hasattr(cause, "category"):
        return str(cause.category or "").strip()
    return ""


def _extract_categories(fishbone_output: Any) -> List[str]:
    if hasattr(fishbone_output, "model_dump"):
        output_dict = fishbone_output.model_dump()
    elif isinstance(fishbone_output, dict):
        output_dict = fishbone_output
    else:
        output_dict = {}
    categories: set = set()
    for key in ("all_categorized_causes", "causes", "high_confidence_causes"):
        for cause in (output_dict.get(key) or []):
            cat = _category_from_cause(cause)
            if cat:
                categories.add(cat)
    return sorted(categories)


def _common_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    def norm(v: Any, default: str = "") -> str:
        return str(v).strip() if v is not None else default

    def norm_opt(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip() or None
        return v

    ev_files = payload.get("evidence_files")
    if ev_files is not None and not isinstance(ev_files, list):
        ev_files = [str(ev_files)]
    return {
        "complaint_id": norm(payload.get("complaint_id")),
        "complaint": norm(payload.get("complaint")),
        "evidence": norm(payload.get("evidence")),
        "sop": norm(payload.get("sop")),
        "fmea_document_path": norm_opt(payload.get("fmea_document_path")),
        "evidence_files": ev_files,
        "logs": norm_opt(payload.get("logs")),
        "reports": norm_opt(payload.get("reports")),
        "process_data": norm_opt(payload.get("process_data")),
        "historical_capa": norm_opt(payload.get("historical_capa")),
        "policies": norm_opt(payload.get("policies")),
        "investigation_records": norm_opt(payload.get("investigation_records")),
        "supporting_system_information": norm_opt(payload.get("supporting_system_information")),
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — INITIALIZE
# Validates input and sets up state
# ══════════════════════════════════════════════════════════════════════════════

def initialize_node(state: RCAGraphState) -> dict:
    print("\n[RCA] Initialize: validating input and setting up state...")

    complaint_id = state.get("complaint_id", "")
    complaint = state.get("complaint", "")
    method = state.get("method", "")

    if not complaint_id:
        return {
            "phase": "error",
            "error": "complaint_id is required",
            "node_log": [{"node": "initialize", "status": "error",
                          "error": "complaint_id required", "timestamp": _now()}],
        }
    if not complaint:
        return {
            "phase": "error",
            "error": "complaint is required",
            "node_log": [{"node": "initialize", "status": "error",
                          "error": "complaint required", "timestamp": _now()}],
        }
    if method not in ("why", "fishbone"):
        return {
            "phase": "error",
            "error": f"method must be 'why' or 'fishbone', got '{method}'",
            "node_log": [{"node": "initialize", "status": "error",
                          "error": "invalid method", "timestamp": _now()}],
        }

    print(f"   complaint_id : {complaint_id}")
    print(f"   method       : {method}")

    return {
        "phase": "running",
        "action_plan_endpoint": ACTION_PLAN_ENDPOINT,
        "action_plan_ready": False,
        "audit_log": [{"time": time.time(), "action": "initialized",
                       "detail": f"method={method}"}],
        "node_log": [{"node": "initialize", "status": "success", "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — RUN FISHBONE (fishbone path only)
# Calls FishboneOrchestratorV3
# ══════════════════════════════════════════════════════════════════════════════

def run_fishbone_node(state: RCAGraphState) -> dict:
    print("\n[RCA] Run Fishbone Orchestrator...")

    complaint_id = state.get("complaint_id", "")
    original_input = state.get("original_input") or {}

    try:
        fishbone_input = FishboneV3Input(**_common_payload(original_input))
        fishbone_output = _get_fishbone_orchestrator().analyze(fishbone_input)
        fishbone_serialized = deep_serialize(fishbone_output)
        categories = _extract_categories(fishbone_serialized)

        fishbone_status = (
            fishbone_serialized.get("status", "")
            if isinstance(fishbone_serialized, dict)
            else ""
        )

        if fishbone_status == "WAIT_FOR_HUMAN":
            message = (
                "Fishbone Analysis paused — causes require review. "
                "Submit cause decisions via POST /fishbone-v3/decide (use same complaint_id). "
                "Call POST /rca/select-category once Fishbone decisions are submitted."
            )
        else:
            message = (
                "Fishbone Analysis complete. "
                "Call POST /rca/select-category to choose a category and proceed to Why Analysis."
            )

        log_transition(complaint_id, "running", "fishbone_running", "fishbone_started")
        return {
            "phase": "fishbone_running",
            "fishbone_output": fishbone_serialized,
            "available_categories": categories,
            "message": message,
            "next_action": "select_category",
            "audit_log": [{"time": time.time(), "action": "fishbone_complete",
                           "detail": f"status={fishbone_status}, categories={categories}"}],
            "node_log": [{"node": "run_fishbone", "status": "success",
                          "categories": categories, "timestamp": _now()}],
        }

    except Exception as exc:
        log_error("run_fishbone_node", str(exc), complaint_id)
        return {
            "phase": "error",
            "error": f"Fishbone failed: {exc}",
            "message": "Fishbone Analysis could not be started.",
            "audit_log": [{"time": time.time(), "action": "fishbone_failed",
                           "detail": str(exc)}],
            "node_log": [{"node": "run_fishbone", "status": "error",
                          "error": str(exc), "timestamp": _now()}],
        }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 3 — AWAIT CATEGORY SELECTION  (HITL #2, fishbone path)
# Pauses until user selects a category, then validates + prepares why input
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_fishbone_state(complaint_id: str, state: RCAGraphState) -> tuple:
    """Return (fishbone_final, categories) — fetching latest from Redis if available."""
    fishbone_final = state.get("fishbone_output") or {}
    fsm = _get_fishbone_session_manager()
    if fsm is not None:
        try:
            latest = fsm.get_state(complaint_id)
            if latest:
                fishbone_final = latest
        except Exception as exc:
            log_error("_resolve_fishbone_state",
                      f"Could not read fishbone session: {exc}", complaint_id)
    cached = list(state.get("available_categories") or [])
    live = _extract_categories(fishbone_final)
    categories = live if live else cached
    return fishbone_final, categories


def _build_enriched_evidence(fishbone_final: Dict[str, Any],
                             selected_category: str,
                             original_input: Dict[str, Any]) -> str:
    """Build evidence string enriched with fishbone category-cause context."""
    categorized_causes = (
        fishbone_final.get("all_categorized_causes")
        or fishbone_final.get("causes")
        or []
    )
    selected_causes = [
        c for c in categorized_causes
        if _category_from_cause(c) == selected_category
    ]
    cause_lines = [f"- {c.get('cause_text', 'Unknown cause')}" for c in selected_causes]
    category_context = (
        f"Fishbone selected category: {selected_category}.\n"
        "Category causes considered:\n"
        + ("\n".join(cause_lines) if cause_lines else "- No category-specific causes available")
    )
    existing = str(original_input.get("evidence") or "").strip()
    return (existing + "\n\n" + category_context) if existing else category_context


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ORCHESTRATOR STATUS HELPERS
# Read live state from child orchestrators so the RCA can gate HITL transitions
# ══════════════════════════════════════════════════════════════════════════════

def _check_fishbone_completion(complaint_id: str) -> Dict[str, Any]:
    """
    Read Fishbone V3 session from Redis and return completion status.
    Returns {"found": bool, "completed": bool, "status": str}.
    If Redis is unavailable or no session exists, optimistically returns completed=True
    so the flow is not blocked on infrastructure issues.
    """
    fsm = _get_fishbone_session_manager()
    if fsm is None:
        return {"found": False, "completed": True, "status": "UNKNOWN"}
    try:
        session_state = fsm.get_state(complaint_id)
    except Exception as exc:
        log_error("_check_fishbone_completion", str(exc), complaint_id)
        return {"found": False, "completed": True, "status": "UNKNOWN"}
    if not session_state:
        # Session may have been cleaned up after completion — allow through
        return {"found": False, "completed": True, "status": "UNKNOWN"}
    status = str(session_state.get("status", "UNKNOWN")).upper()
    return {
        "found": True,
        "completed": status == "COMPLETED",
        "status": status,
    }


def _check_why_completion(why_session_id: str) -> Dict[str, Any]:
    """
    Read Why Analysis V3 LangGraph checkpoint from Redis and return completion status.
    Returns {"found": bool, "completed": bool, "awaiting_human_review": bool,
             "status": str, "final_output": dict|None}.
    If the checkpoint cannot be read, optimistically returns found=False so the flow
    is not blocked — the user can still proceed.
    """
    try:
        # Lazy import avoids a circular import at module load time
        from orchestrator.why_analysis_v3.orchestrator import (
            orchestrator_graph as _why_graph,
        )
        snapshot = _why_graph.get_state({"configurable": {"thread_id": why_session_id}})
        if snapshot is None or not snapshot.values:
            return {"found": False, "completed": False, "awaiting_human_review": False,
                    "status": "unknown", "final_output": None}
        values = snapshot.values
        status = str(values.get("status", "unknown"))
        awaiting = bool(values.get("awaiting_human_review", False))
        # completed = terminal status with no pending human review
        completed = status in ("completed", "ai_flagged") and not awaiting
        return {
            "found": True,
            "completed": completed,
            "awaiting_human_review": awaiting,
            "status": status,
            "final_output": values.get("final_output"),
        }
    except Exception as exc:
        log_error("_check_why_completion", str(exc))
        return {"found": False, "completed": False, "awaiting_human_review": False,
                "status": "unknown", "final_output": None, "error": str(exc)}


def await_category_selection_node(state: RCAGraphState) -> dict:
    print("\n[RCA] Await Category Selection (HITL #2)...")

    complaint_id = state.get("complaint_id", "")
    selected_category = state.get("selected_category")

    if not selected_category:
        # ── Pause: waiting for user to pick a category ────────────────────────
        return {
            "phase": "awaiting_category_selection",
            "next_action": "select_category",
            "message": "Fishbone complete. Select a category via POST /rca/select-category.",
            "node_log": [{"node": "await_category_selection", "status": "awaiting_input",
                          "timestamp": _now()}],
        }

    # ── Guard: Fishbone must be COMPLETED before we accept a category ─────────
    fishbone_status = _check_fishbone_completion(complaint_id)
    if fishbone_status.get("found") and not fishbone_status.get("completed"):
        return {
            "phase": "awaiting_category_selection",
            "next_action": "select_category",
            "message": (
                f"Fishbone Analysis is still awaiting human decisions "
                f"(status: {fishbone_status.get('status')}). "
                "Submit cause decisions first via POST /fishbone-v3/decide, "
                "then call POST /rca/select-category."
            ),
            "node_log": [{"node": "await_category_selection", "status": "blocked",
                          "reason": "fishbone_not_complete",
                          "fishbone_status": fishbone_status.get("status"),
                          "timestamp": _now()}],
        }

    # ── User has provided a category: validate + enrich evidence ─────────────
    fishbone_final, categories = _resolve_fishbone_state(complaint_id, state)

    if not categories:
        return {
            "phase": "error",
            "error": "No categories found in the Fishbone output.",
            "node_log": [{"node": "await_category_selection", "status": "error",
                          "error": "no_categories", "timestamp": _now()}],
        }

    if selected_category not in categories:
        return {
            "phase": "error",
            "error": f"Selected category '{selected_category}' is not valid. Available: {categories}",
            "node_log": [{"node": "await_category_selection", "status": "error",
                          "error": "invalid_category", "timestamp": _now()}],
        }

    enriched_evidence = _build_enriched_evidence(
        fishbone_final, selected_category, state.get("original_input") or {}
    )

    log_transition(complaint_id, "awaiting_category_selection",
                   "category_selected", f"category={selected_category}")
    return {
        "phase": "category_selected",
        "fishbone_output": deep_serialize(fishbone_final),
        "available_categories": categories,
        "enriched_evidence": enriched_evidence,
        "audit_log": [{"time": time.time(), "action": "category_selected",
                       "detail": f"category={selected_category}"}],
        "node_log": [{"node": "await_category_selection", "status": "selected",
                      "category": selected_category, "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 4 — RUN WHY ANALYSIS
# Calls WhyAnalysisV3Orchestrator (handles fishbone + direct why paths)
# ══════════════════════════════════════════════════════════════════════════════

def run_why_node(state: RCAGraphState) -> dict:
    print("\n[RCA] Run Why Analysis Orchestrator...")

    complaint_id = state.get("complaint_id", "")
    original_input = state.get("original_input") or {}
    selected_category = state.get("selected_category")

    try:
        base_payload = _common_payload(original_input)

        # If coming from fishbone, use the enriched evidence (context + category causes)
        if selected_category:
            enriched = state.get("enriched_evidence") or base_payload.get("evidence") or ""
            base_payload["evidence"] = enriched

        why_input = WhyAnalysisV3Input(**base_payload)
        why_output = _get_why_orchestrator().analyze(why_input)
        why_serialized = deep_serialize(why_output)
        why_session_id = (
            why_serialized.get("session_id")
            if isinstance(why_serialized, dict)
            else None
        )

        log_transition(complaint_id, state.get("phase", "running"), "why_running", "why_started")
        return {
            "phase": "why_running",
            "why_output": why_serialized,
            "why_session_id": why_session_id,
            "next_action": "proceed_action_plan",
            "message": (
                "Why Analysis started. "
                "Use POST /why-analysis-v3/human-review for internal cause-selection steps. "
                "Call POST /rca/proceed-action-plan once Why Analysis is complete."
            ),
            "audit_log": [{"time": time.time(), "action": "why_started",
                           "detail": f"why_session_id={why_session_id}"}],
            "node_log": [{"node": "run_why", "status": "success",
                          "why_session_id": why_session_id, "timestamp": _now()}],
        }

    except Exception as exc:
        log_error("run_why_node", str(exc), complaint_id)
        return {
            "phase": "error",
            "error": f"Why Analysis failed: {exc}",
            "message": "Why Analysis could not be started.",
            "audit_log": [{"time": time.time(), "action": "why_failed",
                           "detail": str(exc)}],
            "node_log": [{"node": "run_why", "status": "error",
                          "error": str(exc), "timestamp": _now()}],
        }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 5 — AWAIT ACTION PLAN CONFIRMATION  (HITL #3)
# Pauses until user confirms or rejects proceeding to the Action Plan
# ══════════════════════════════════════════════════════════════════════════════

def await_action_plan_node(state: RCAGraphState) -> dict:
    print("\n[RCA] Await Action Plan Confirmation (HITL #3)...")

    complaint_id = state.get("complaint_id", "")
    action_plan_confirmed = state.get("action_plan_confirmed")

    if action_plan_confirmed is None:
        # ── Pause: waiting for user confirmation ──────────────────────────────
        return {
            "phase": "awaiting_action_plan_confirmation",
            "next_action": "proceed_action_plan",
            "message": (
                "Why Analysis started. "
                "Once Why Analysis (including /why-analysis-v3/human-review) is complete, "
                "call POST /rca/proceed-action-plan to confirm or reject the Action Plan."
            ),
            "node_log": [{"node": "await_action_plan", "status": "awaiting_input",
                          "timestamp": _now()}],
        }

    # ── Guard: Why Analysis must be complete before we allow action plan ──────
    why_session_id = state.get("why_session_id")
    refreshed_why_output: Optional[Dict[str, Any]] = None

    if why_session_id:
        why_status = _check_why_completion(why_session_id)
        print(f"   [RCA] Why status check: {why_status.get('status')} "
              f"| awaiting_human_review={why_status.get('awaiting_human_review')} "
              f"| completed={why_status.get('completed')}")
        if why_status.get("found") and not why_status.get("completed"):
            return {
                "phase": "awaiting_action_plan_confirmation",
                "next_action": "proceed_action_plan",
                "message": (
                    f"Why Analysis is still in progress "
                    f"(status: {why_status.get('status')}, "
                    f"awaiting_human_review: {why_status.get('awaiting_human_review')}). "
                    "Complete Why Analysis via POST /why-analysis-v3/human-review, "
                    "then call POST /rca/proceed-action-plan."
                ),
                "node_log": [{"node": "await_action_plan", "status": "blocked",
                              "reason": "why_not_complete",
                              "why_status": why_status.get("status"),
                              "awaiting_human_review": why_status.get("awaiting_human_review"),
                              "timestamp": _now()}],
            }
        # Sync in the latest completed Why output so finalize has the full result
        if why_status.get("found") and why_status.get("final_output"):
            refreshed_why_output = deep_serialize(why_status["final_output"])
            print(f"   [RCA] Refreshed why_output from completed checkpoint.")

    # ── User has decided ──────────────────────────────────────────────────────
    if not action_plan_confirmed:
        log_transition(complaint_id, "awaiting_action_plan_confirmation",
                       "completed", "action_plan_rejected")
        return {
            "phase": "completed",
            "action_plan_ready": False,
            "why_output": refreshed_why_output or state.get("why_output"),
            "next_action": None,
            "message": "Action plan was not confirmed. RCA session remains open.",
            "audit_log": [{"time": time.time(), "action": "action_plan_rejected",
                           "detail": "User rejected"}],
            "node_log": [{"node": "await_action_plan", "status": "rejected",
                          "timestamp": _now()}],
        }

    log_transition(complaint_id, "awaiting_action_plan_confirmation",
                   "completed", "action_plan_confirmed")
    return {
        "phase": "completed",
        "action_plan_ready": True,
        "action_plan_endpoint": ACTION_PLAN_ENDPOINT,
        "why_output": refreshed_why_output or state.get("why_output"),
        "next_action": None,
        "message": "RCA complete. Proceeding to Action Plan.",
        "audit_log": [{"time": time.time(), "action": "action_plan_confirmed",
                       "detail": "User confirmed handoff to action plan"}],
        "node_log": [{"node": "await_action_plan", "status": "confirmed",
                      "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 6 — FINALIZE
# Assembles the final API response dict
# ══════════════════════════════════════════════════════════════════════════════

def finalize_node(state: RCAGraphState) -> dict:
    print("\n[RCA] Finalize: building final output...")

    execution_time = round(time.time() - float(state.get("start_time") or time.time()), 4)

    final_output = deep_serialize({
        "complaint_id": state.get("complaint_id", ""),
        "phase": state.get("phase", "idle"),
        "selected_method": state.get("method"),
        "message": state.get("message"),
        "available_categories": state.get("available_categories", []),
        "selected_category": state.get("selected_category"),
        "fishbone_output": state.get("fishbone_output"),
        "why_output": state.get("why_output"),
        "why_session_id": state.get("why_session_id"),
        "action_plan_ready": bool(state.get("action_plan_ready", False)),
        "action_plan_endpoint": state.get("action_plan_endpoint", ACTION_PLAN_ENDPOINT),
        "next_action": state.get("next_action"),
        "error": state.get("error"),
        "updated_at": time.time(),
        "execution_time_seconds": execution_time,
    })

    print(f"   Final phase      : {final_output['phase']}")
    print(f"   Execution time   : {execution_time:.2f}s")

    return {
        "final_output": final_output,
        "updated_at": time.time(),
        "node_log": [{"node": "finalize", "status": "complete", "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# All routing logic lives here — not inside node functions
# ══════════════════════════════════════════════════════════════════════════════

def route_after_initialize(state: RCAGraphState) -> str:
    if state.get("phase") == "error":
        return "finalize"
    return "run_fishbone" if state.get("method") == "fishbone" else "run_why"


def route_after_fishbone(state: RCAGraphState) -> str:
    if state.get("phase") == "error":
        return "finalize"
    return "await_category_selection"


def route_after_await_category_selection(state: RCAGraphState) -> str:
    if state.get("phase") == "error":
        return "finalize"
    if state.get("phase") == "awaiting_category_selection":
        return END
    return "run_why"


def route_after_run_why(state: RCAGraphState) -> str:
    if state.get("phase") == "error":
        return "finalize"
    return "await_action_plan"


def route_after_await_action_plan(state: RCAGraphState) -> str:
    if state.get("phase") == "awaiting_action_plan_confirmation":
        return END
    return "finalize"


def route_after_finalize(state: RCAGraphState) -> str:
    return END


# ══════════════════════════════════════════════════════════════════════════════
# BUILD GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def build_orchestrator():
    """
    Assembles the full RCA coordinator LangGraph.

    Topology:
        START
          └─► initialize
                ├─► (fishbone) → run_fishbone → await_category_selection
                │                                 ├─► END  (HITL #2 pause)
                │                                 └─► run_why
                │                                       └─► await_action_plan
                │                                             ├─► END  (HITL #3 pause)
                │                                             └─► finalize → END
                └─► (why)    → run_why
                                └─► await_action_plan
                                      ├─► END  (HITL #3 pause)
                                      └─► finalize → END
    """
    g = StateGraph(RCAGraphState)

    # ── Register nodes ────────────────────────────────────────────────────────
    g.add_node("initialize", initialize_node)
    g.add_node("run_fishbone", run_fishbone_node)
    g.add_node("await_category_selection", await_category_selection_node)
    g.add_node("run_why", run_why_node)
    g.add_node("await_action_plan", await_action_plan_node)
    g.add_node("finalize", finalize_node)

    # ── Entry ─────────────────────────────────────────────────────────────────
    g.add_edge(START, "initialize")

    # ── Routing ───────────────────────────────────────────────────────────────
    g.add_conditional_edges(
        "initialize",
        route_after_initialize,
        {
            "run_fishbone": "run_fishbone",
            "run_why": "run_why",
            "finalize": "finalize",
        },
    )

    g.add_conditional_edges(
        "run_fishbone",
        route_after_fishbone,
        {
            "await_category_selection": "await_category_selection",
            "finalize": "finalize",
        },
    )

    g.add_conditional_edges(
        "await_category_selection",
        route_after_await_category_selection,
        {
            "run_why": "run_why",
            "finalize": "finalize",
            END: END,
        },
    )

    g.add_conditional_edges(
        "run_why",
        route_after_run_why,
        {
            "await_action_plan": "await_action_plan",
            "finalize": "finalize",
        },
    )

    g.add_conditional_edges(
        "await_action_plan",
        route_after_await_action_plan,
        {
            "finalize": "finalize",
            END: END,
        },
    )

    g.add_conditional_edges(
        "finalize",
        route_after_finalize,
        {END: END},
    )

    # ── Compile with Redis checkpointing ──────────────────────────────────────
    checkpointer = RedisSaver(_REDIS_URL)
    checkpointer.setup()
    return g.compile(checkpointer=checkpointer)


# ── Module-level graph instance ───────────────────────────────────────────────
orchestrator_graph = build_orchestrator()
