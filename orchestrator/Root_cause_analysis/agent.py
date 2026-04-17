"""
Root Cause Analysis coordinator agent.

Thin wrapper around the LangGraph orchestrator graph — mirrors the interface
used by why_analysis_v3 and other graph-based orchestrators.

3 parent-level HITL points:
  1. start()                         (POST /rca/start)
  2. select_category_and_start_why() (POST /rca/select-category)
  3. proceed_to_action_plan()        (POST /rca/proceed-action-plan)

Child-orchestrator internal HITL is NOT proxied here:
  - Fishbone cause decisions → POST /fishbone-v3/decide
  - Why cause selection      → POST /why-analysis-v3/human-review
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from .orchestrator import deep_serialize, orchestrator_graph, ACTION_PLAN_ENDPOINT
from .schemas import (
    RCAProceedActionPlanInput,
    RCASelectCategoryInput,
    RCAStartInput,
)
from .logger import log_error


class RootCauseAnalysisCoordinator:
    """
    RCA coordinator wrapping the LangGraph orchestrator graph.
    Session state is persisted via the Redis checkpointer using complaint_id
    as the thread_id.
    """

    def __init__(self):
        self.graph = orchestrator_graph

    # ── HITL #1 ───────────────────────────────────────────────────────────────

    def start(self, input_data: RCAStartInput, session_id: str | None = None) -> Dict[str, Any]:
        """
        HITL #1: User selects 'why' or 'fishbone' and kicks off the analysis.

        why path:
          Runs Why Analysis immediately. Its internal HITL is handled via
          POST /why-analysis-v3/human-review.
          Call POST /rca/proceed-action-plan once Why is finished.

        fishbone path:
          Runs Fishbone Analysis. Its internal HITL is handled via
          POST /fishbone-v3/decide.
          Call POST /rca/select-category once Fishbone + decisions are done.
        """
        complaint_id = input_data.complaint_id
        if session_id is None:
            session_id = f"{complaint_id}_{uuid.uuid4().hex[:8]}"
        try:
            initial_state = {
                "complaint_id": complaint_id,
                "session_id": session_id,
                "complaint": input_data.complaint,
                "evidence": input_data.evidence or "",
                "sop": input_data.sop or "",
                "fmea_document_path": input_data.fmea_document_path,
                "method": input_data.method,
                "evidence_files": input_data.evidence_files,
                "logs": input_data.logs,
                "reports": input_data.reports,
                "process_data": input_data.process_data,
                "historical_capa": input_data.historical_capa,
                "policies": input_data.policies,
                "investigation_records": input_data.investigation_records,
                "supporting_system_information": input_data.supporting_system_information,
                "original_input": deep_serialize(input_data.model_dump()),
                "start_time": time.time(),
                "action_plan_endpoint": ACTION_PLAN_ENDPOINT,
                "action_plan_ready": False,
                "available_categories": [],
                "audit_log": [],
                "node_log": [],
            }
            config = {"configurable": {"thread_id": session_id}}
            final_state = self.graph.invoke(initial_state, config=config)
            return self._build_response(final_state)

        except Exception as exc:
            log_error("start", str(exc), complaint_id)
            return {
                "complaint_id": complaint_id,
                "session_id": session_id,
                "phase": "error",
                "error": f"Start failed: {exc}",
                "message": "RCA analysis could not be started.",
                "available_categories": [],
                "action_plan_ready": False,
                "action_plan_endpoint": ACTION_PLAN_ENDPOINT,
                "updated_at": time.time(),
            }

    # ── HITL #2 ───────────────────────────────────────────────────────────────

    def select_category_and_start_why(self, input_data: RCASelectCategoryInput) -> Dict[str, Any]:
        """
        HITL #2 (fishbone path): After Fishbone + /fishbone-v3/decide are done,
        user selects which category to proceed with into Why Analysis.
        """
        complaint_id = input_data.complaint_id
        if not input_data.session_id:
            raise ValueError("session_id is required. Use the session_id returned by POST /rca/start.")
        thread_id = input_data.session_id
        try:
            config = {"configurable": {"thread_id": thread_id}}
            self.graph.update_state(config, {
                "selected_category":   input_data.category,
                "selected_cause_id":   input_data.selected_cause_id,
                "selected_cause_text": input_data.selected_cause_text,
            })
            final_state = self.graph.invoke(None, config=config)
            return self._build_response(final_state)

        except KeyError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            log_error("select_category_and_start_why", str(exc), complaint_id)
            return {
                "complaint_id": complaint_id,
                "session_id": input_data.session_id,
                "phase": "error",
                "error": f"Category selection failed: {exc}",
                "message": "Could not start Why Analysis from selected category.",
                "available_categories": [],
                "action_plan_ready": False,
                "action_plan_endpoint": ACTION_PLAN_ENDPOINT,
                "updated_at": time.time(),
            }

    # ── HITL #3 ───────────────────────────────────────────────────────────────

    def proceed_to_action_plan(self, input_data: RCAProceedActionPlanInput) -> Dict[str, Any]:
        """
        HITL #3: After Why Analysis (including its own HITL) is done,
        user confirms whether to proceed to the Action Plan.
        """
        complaint_id = input_data.complaint_id
        if not input_data.session_id:
            raise ValueError("session_id is required. Use the session_id returned by POST /rca/start.")
        thread_id = input_data.session_id
        try:
            config = {"configurable": {"thread_id": thread_id}}
            self.graph.update_state(config, {"action_plan_confirmed": input_data.confirmed})
            final_state = self.graph.invoke(None, config=config)
            return self._build_response(final_state)

        except KeyError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            log_error("proceed_to_action_plan", str(exc), complaint_id)
            return {
                "complaint_id": complaint_id,
                "session_id": input_data.session_id,
                "phase": "error",
                "error": f"Proceed to action plan failed: {exc}",
                "message": "Could not proceed to action plan.",
                "available_categories": [],
                "action_plan_ready": False,
                "action_plan_endpoint": ACTION_PLAN_ENDPOINT,
                "updated_at": time.time(),
            }

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self, complaint_id: str, session_id: str | None = None) -> Dict[str, Any]:
        """Read current session state from the Redis checkpoint."""
        thread_id = session_id or complaint_id
        try:
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = self.graph.get_state(config)
            if not snapshot or not snapshot.values:
                raise KeyError(f"No RCA session found for '{thread_id}'")
            return self._build_response(snapshot.values)
        except KeyError:
            raise
        except Exception as exc:
            log_error("status", str(exc), complaint_id)
            raise KeyError(
                f"Could not retrieve RCA session for '{thread_id}': {exc}"
            ) from exc

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_response(state: Dict[str, Any]) -> Dict[str, Any]:
        """Build API response dict from graph state or final_output."""
        if state.get("final_output"):
            return state["final_output"]
        return {
            "complaint_id": state.get("complaint_id", ""),
            "session_id": state.get("session_id"),
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
            "updated_at": float(state.get("updated_at") or time.time()),
        }
