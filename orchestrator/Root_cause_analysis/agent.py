"""
Root Cause Analysis coordinator agent.

3 HITL points:
  1. POST /rca/start         — user picks method (why | fishbone)
  2. POST /rca/select-category  — (fishbone path) user picks category after fishbone + cause-decisions done
  3. POST /rca/proceed-action-plan — user confirms proceeding to action plan after why analysis done

Child-orchestrator internal HITL is NOT proxied here:
  - Fishbone cause decisions → POST /fishbone-v3/decide
  - Why cause selection      → POST /why-analysis-v3/human-review
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from orchestrator.fishbone_v3.agent import FishboneOrchestratorV3
from orchestrator.fishbone_v3.session_memory import SessionMemoryManagerV3 as FishboneSessionManager
from orchestrator.fishbone_v3.schemas import FishboneV3Input
from orchestrator.why_analysis_v3.agent import WhyAnalysisV3Orchestrator
from orchestrator.why_analysis_v3.schemas import WhyAnalysisV3Input

from .logger import log_error, log_info, log_transition
from .schemas import (
    RCAProceedActionPlanInput,
    RCASelectCategoryInput,
    RCAStartInput,
)
from .session_memory import RCASessionMemoryManager
from .state import RCASessionState


class RootCauseAnalysisCoordinator:
    """
    Thin RCA coordinator with exactly 3 parent-level HITL points.

    Child orchestrators handle their own internal HITL through their own routes:
      /fishbone-v3/decide          (fishbone cause decisions)
      /why-analysis-v3/human-review (why cause selection)
    """

    ACTION_PLAN_ENDPOINT = "/action_plan"

    def __init__(self):
        self.fishbone_orchestrator = FishboneOrchestratorV3()
        self.why_orchestrator = WhyAnalysisV3Orchestrator()
        self.session_manager = RCASessionMemoryManager()

        # Read-only access to fishbone's Redis session so select-category can
        # retrieve the final fishbone output after the frontend completes /fishbone-v3/decide.
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.fishbone_session_manager = FishboneSessionManager(redis_url=redis_url)
        except Exception as exc:
            log_error("init_fishbone_session_manager", str(exc))
            self.fishbone_session_manager = None

    def start(self, input_data: RCAStartInput) -> Dict[str, Any]:
        """
        HITL #1: User selects 'why' or 'fishbone' and kicks off the analysis.

        why path:
          Starts Why Analysis immediately. Why's internal HITL (cause selection)
          is handled via POST /why-analysis-v3/human-review.
          Call POST /rca/proceed-action-plan once Why Analysis is finished.

        fishbone path:
          Starts Fishbone Analysis. Fishbone's internal HITL (cause decisions)
          is handled via POST /fishbone-v3/decide.
          Call POST /rca/select-category once Fishbone + decisions are finished.
        """
        complaint_id = input_data.complaint_id
        state = self._init_state(input_data.model_dump(), selected_method=input_data.method)

        try:
            if input_data.method == "why":
                return self._run_why_start(state, input_data)
            else:
                return self._run_fishbone_start(state, input_data)
        except Exception as exc:
            log_error("start", str(exc), complaint_id)
            state["phase"] = "error"
            state["error"] = f"Start failed: {exc}"
            state["message"] = "RCA analysis could not be started."
            self._append_audit(state, "start_failed", str(exc))
            self.session_manager.save_state(complaint_id, state)
            return self._response(state)

    def _run_why_start(self, state: RCASessionState, input_data: RCAStartInput) -> Dict[str, Any]:
        complaint_id = input_data.complaint_id

        why_input = WhyAnalysisV3Input(**self._common_payload(input_data.model_dump()))
        why_output = self.why_orchestrator.analyze(why_input)

        state["why_output"] = self._json_safe(why_output)
        state["why_session_id"] = why_output.get("session_id")
        state["phase"] = "why_running"
        state["next_action"] = "proceed_action_plan"
        state["message"] = (
            "Why Analysis started. "
            "Use POST /why-analysis-v3/human-review (session_id in response) "
            "for internal cause-selection steps. "
            "Call POST /rca/proceed-action-plan once Why Analysis is complete."
        )

        self._append_audit(state, "start_why", f"why_session_id={state['why_session_id']}")
        self.session_manager.save_state(complaint_id, state)
        log_transition(complaint_id, "idle", "why_running", "why_selected")
        return self._response(state)

    def _run_fishbone_start(self, state: RCASessionState, input_data: RCAStartInput) -> Dict[str, Any]:
        complaint_id = input_data.complaint_id

        fishbone_input = FishboneV3Input(**self._common_payload(input_data.model_dump()))
        fishbone_output = self.fishbone_orchestrator.analyze(fishbone_input)

        state["fishbone_output"] = self._json_safe(fishbone_output)

        # Capture any categories already available from the initial analyse call.
        categories = self._extract_categories(fishbone_output)
        state["available_categories"] = categories

        state["phase"] = "fishbone_running"
        state["next_action"] = "select_category"

        fishbone_status = fishbone_output.get("status", "") if isinstance(fishbone_output, dict) else ""
        if fishbone_status == "WAIT_FOR_HUMAN":
            state["message"] = (
                "Fishbone Analysis paused — high-confidence causes require review. "
                "Submit cause decisions via POST /fishbone-v3/decide (use same complaint_id). "
                "Call POST /rca/select-category once Fishbone decisions are submitted."
            )
        else:
            state["message"] = (
                "Fishbone Analysis complete. "
                "Call POST /rca/select-category to choose a category and proceed to Why Analysis."
            )

        self._append_audit(state, "start_fishbone", f"fishbone_status={fishbone_status}, categories={categories}")
        self.session_manager.save_state(complaint_id, state)
        log_transition(complaint_id, "idle", "fishbone_running", "fishbone_selected")
        return self._response(state)

    def select_category_and_start_why(self, input_data: RCASelectCategoryInput) -> Dict[str, Any]:
        """
        HITL #2 (fishbone path): After Fishbone + /fishbone-v3/decide are done,
        user selects which category to proceed with into Why Analysis.
        """
        complaint_id = input_data.complaint_id
        state = self._require_state(complaint_id)

        if state.get("phase") != "fishbone_running":
            raise ValueError("Category selection is only allowed when phase is 'fishbone_running'.")

        # Try to get the final fishbone output (post-decisions) from fishbone's own Redis.
        # Fall back to the snapshot stored when we called analyze().
        fishbone_final = self._get_final_fishbone_output(complaint_id, state)
        categories = self._extract_categories(fishbone_final)

        if not categories:
            raise ValueError("No categories found in the Fishbone output.")

        if input_data.category not in categories:
            raise ValueError(
                f"Selected category '{input_data.category}' is not valid. "
                f"Available: {categories}"
            )

        selected_category = input_data.category
        original_input = state.get("original_input") or {}
        previous_phase = state.get("phase", "fishbone_running")

        try:
            why_input = self._build_why_input_from_category(original_input, fishbone_final, selected_category)
            why_output = self.why_orchestrator.analyze(why_input)

            state["fishbone_output"] = self._json_safe(fishbone_final)
            state["available_categories"] = categories
            state["selected_category"] = selected_category
            state["why_output"] = self._json_safe(why_output)
            state["why_session_id"] = why_output.get("session_id")
            state["phase"] = "why_running"
            state["next_action"] = "proceed_action_plan"
            state["message"] = (
                f"Why Analysis started from Fishbone category '{selected_category}'. "
                "Use POST /why-analysis-v3/human-review for internal cause-selection steps. "
                "Call POST /rca/proceed-action-plan once Why Analysis is complete."
            )

            self._append_audit(state, "select_category", f"category={selected_category}, why_session_id={state['why_session_id']}")
            self.session_manager.save_state(complaint_id, state)
            log_transition(complaint_id, previous_phase, "why_running", "category_selected")
            return self._response(state)

        except Exception as exc:
            log_error("select_category_and_start_why", str(exc), complaint_id)
            state["phase"] = "error"
            state["error"] = f"Why launch from selected category failed: {exc}"
            state["message"] = "Could not start Why Analysis from selected category."
            self._append_audit(state, "select_category_failed", str(exc))
            self.session_manager.save_state(complaint_id, state)
            return self._response(state)

    def proceed_to_action_plan(self, input_data: RCAProceedActionPlanInput) -> Dict[str, Any]:
        """
        HITL #3: After Why Analysis (including its own internal HITL) is done,
        user confirms whether to proceed to the Action Plan.
        """
        complaint_id = input_data.complaint_id
        state = self._require_state(complaint_id)

        if state.get("phase") != "why_running":
            raise ValueError("Proceed to action plan is only allowed when phase is 'why_running'.")

        previous_phase = state.get("phase", "why_running")

        if not input_data.confirmed:
            state["message"] = "Action plan was not confirmed. RCA session remains open."
            self.session_manager.save_state(complaint_id, state)
            return self._response(state)

        state["action_plan_ready"] = True
        state["action_plan_endpoint"] = self.ACTION_PLAN_ENDPOINT
        state["phase"] = "completed"
        state["next_action"] = None
        state["message"] = "RCA complete. Proceeding to Action Plan."

        self._append_audit(state, "proceed_action_plan", "User confirmed handoff to action plan")
        self.session_manager.save_state(complaint_id, state)
        log_transition(complaint_id, previous_phase, "completed", "action_plan_confirmed")
        return self._response(state)

    def status(self, complaint_id: str) -> Dict[str, Any]:
        state = self._require_state(complaint_id)
        return self._response(state)

    def _get_final_fishbone_output(self, complaint_id: str, state: RCASessionState) -> Dict[str, Any]:
        """
        Fetch the latest fishbone state from fishbone's own Redis session.
        This captures any updates made after /fishbone-v3/decide was called.
        Falls back to the snapshot stored in the RCA state if Redis is unavailable.
        """
        if self.fishbone_session_manager is not None:
            try:
                fishbone_state = self.fishbone_session_manager.get_state(complaint_id)
                if fishbone_state:
                    return fishbone_state
            except Exception as exc:
                log_error("_get_final_fishbone_output", f"Could not read fishbone session: {exc}", complaint_id)

        # Fallback: use what we stored when analyze() was called
        return state.get("fishbone_output") or {}

    def _build_why_input_from_category(
        self,
        original_input: Dict[str, Any],
        fishbone_output: Dict[str, Any],
        selected_category: str,
    ) -> WhyAnalysisV3Input:
        base_payload = self._common_payload(original_input)

        categorized_causes = (
            fishbone_output.get("all_categorized_causes")
            or fishbone_output.get("causes")
            or []
        )
        selected_causes = [
            cause for cause in categorized_causes
            if str(cause.get("category", "")).strip() == selected_category
        ]

        cause_lines = [f"- {c.get('cause_text', 'Unknown cause')}" for c in selected_causes]
        category_context = (
            f"Fishbone selected category: {selected_category}.\n"
            "Category causes considered:\n"
            + ("\n".join(cause_lines) if cause_lines else "- No category-specific causes available")
        )

        existing_evidence = base_payload.get("evidence") or ""
        base_payload["evidence"] = (existing_evidence + "\n\n" + category_context) if existing_evidence else category_context

        return WhyAnalysisV3Input(**base_payload)

    @staticmethod
    def _category_from_cause(cause: Any) -> str:
        if isinstance(cause, dict):
            return str(cause.get("category", "")).strip()
        if hasattr(cause, "category"):
            return str(cause.category or "").strip()
        return ""

    @staticmethod
    def _extract_categories(fishbone_output: Any) -> List[str]:
        if hasattr(fishbone_output, "get"):
            output_dict = fishbone_output
        elif hasattr(fishbone_output, "model_dump"):
            output_dict = fishbone_output.model_dump()
        else:
            output_dict = {}

        categories: set = set()
        for key in ("all_categorized_causes", "causes", "high_confidence_causes"):
            for cause in (output_dict.get(key) or []):
                category = RootCauseAnalysisCoordinator._category_from_cause(cause)
                if category:
                    categories.add(category)
        return sorted(categories)

    @staticmethod
    def _common_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        evidence_files = RootCauseAnalysisCoordinator._normalize_evidence_files(payload.get("evidence_files"))
        return {
            "complaint_id": RootCauseAnalysisCoordinator._normalize_text(payload.get("complaint_id"), default=""),
            "complaint": RootCauseAnalysisCoordinator._normalize_text(payload.get("complaint"), default=""),
            "evidence": RootCauseAnalysisCoordinator._normalize_text(payload.get("evidence"), default=""),
            "sop": RootCauseAnalysisCoordinator._normalize_text(payload.get("sop"), default=""),
            "fmea_document_path": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("fmea_document_path")),
            "evidence_files": evidence_files,
            "logs": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("logs")),
            "reports": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("reports")),
            "process_data": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("process_data")),
            "historical_capa": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("historical_capa")),
            "policies": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("policies")),
            "investigation_records": RootCauseAnalysisCoordinator._normalize_optional_text(payload.get("investigation_records")),
            "supporting_system_information": RootCauseAnalysisCoordinator._normalize_optional_text(
                payload.get("supporting_system_information")
            ),
        }

    @staticmethod
    def _init_state(original_input: Dict[str, Any], selected_method: str) -> RCASessionState:
        return {
            "complaint_id": original_input.get("complaint_id", ""),
            "phase": "idle",
            "selected_method": selected_method,
            "message": "",
            "original_input": RootCauseAnalysisCoordinator._json_safe(original_input),
            "fishbone_output": None,
            "available_categories": [],
            "selected_category": None,
            "why_output": None,
            "why_session_id": None,
            "action_plan_ready": False,
            "action_plan_endpoint": RootCauseAnalysisCoordinator.ACTION_PLAN_ENDPOINT,
            "next_action": None,
            "error": None,
            "updated_at": time.time(),
            "audit_log": [],
        }

    @staticmethod
    def _append_audit(state: RCASessionState, action: str, detail: str) -> None:
        audit_log = state.get("audit_log") or []
        audit_log.append({"time": time.time(), "action": action, "detail": detail})
        state["audit_log"] = audit_log

    def _require_state(self, complaint_id: str) -> RCASessionState:
        state = self.session_manager.get_state(complaint_id)
        if not state:
            raise KeyError(f"No RCA session found for complaint_id '{complaint_id}'")
        return state

    @staticmethod
    def _response(state: RCASessionState) -> Dict[str, Any]:
        return {
            "complaint_id": state.get("complaint_id", ""),
            "phase": state.get("phase", "idle"),
            "selected_method": state.get("selected_method"),
            "message": state.get("message"),
            "available_categories": state.get("available_categories", []),
            "selected_category": state.get("selected_category"),
            "fishbone_output": state.get("fishbone_output"),
            "why_output": state.get("why_output"),
            "why_session_id": state.get("why_session_id"),
            "action_plan_ready": bool(state.get("action_plan_ready", False)),
            "action_plan_endpoint": state.get(
                "action_plan_endpoint", RootCauseAnalysisCoordinator.ACTION_PLAN_ENDPOINT
            ),
            "next_action": state.get("next_action"),
            "error": state.get("error"),
            "updated_at": float(state.get("updated_at") or time.time()),
        }

    @staticmethod
    def _json_safe(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): RootCauseAnalysisCoordinator._json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [RootCauseAnalysisCoordinator._json_safe(v) for v in obj]
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            return RootCauseAnalysisCoordinator._json_safe(obj.model_dump())
        return str(obj)

    @staticmethod
    def _normalize_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            text = value.strip()
            return text if text else default
        if isinstance(value, (list, tuple, set)):
            parts = [RootCauseAnalysisCoordinator._normalize_text(v, default="") for v in value]
            joined = "\n".join([part for part in parts if part])
            return joined if joined else default
        if isinstance(value, dict):
            try:
                return json.dumps(value, ensure_ascii=True)
            except Exception:
                return str(value)
        return str(value)

    @staticmethod
    def _normalize_optional_text(value: Any) -> str | None:
        normalized = RootCauseAnalysisCoordinator._normalize_text(value, default="")
        return normalized if normalized else None

    @staticmethod
    def _normalize_evidence_files(value: Any) -> List[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        if isinstance(value, str):
            return [value] if value.strip() else None
        return None
