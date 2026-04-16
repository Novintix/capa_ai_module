"""
Coordinator wrapper for unified RCA v2 LangGraph orchestrator.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from orchestrator.Root_cause_analysis.logger import log_error
from .orchestrator_v2 import deep_serialize, orchestrator_graph_v2
from .schemas_v2 import (
    RCAFishboneSelectionInputV2,
    RCAStartInputV2,
    RCAWhyDecisionInputV2,
)


class RootCauseAnalysisCoordinatorV2:
    """Thin coordinator around RCA v2 LangGraph with Redis checkpointing."""

    def __init__(self):
        self.graph = orchestrator_graph_v2

    def start_v2(self, input_data: RCAStartInputV2, session_id: str | None = None) -> Dict[str, Any]:
        complaint_id = input_data.complaint_id
        if session_id is None:
            session_id = f"{complaint_id}_{uuid.uuid4().hex[:8]}"

        try:
            initial_state = {
                "complaint_id": complaint_id,
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
                "session_id": session_id,
                "start_time": time.time(),
                "updated_at": time.time(),
                "status": "running",
                "phase": "starting",
                "message": None,
                "error": None,
                "next_action": None,
                "awaiting_human_review": False,
                "hitl_type": None,
                "stopping_reason": None,
                "ai_flagged": False,
                "why_chain": [],
                "why_iterations": [],
                "timeline": [],
                "audit_log": [],
                "node_log": [],
            }
            config = {"configurable": {"thread_id": session_id}}
            final_state = self.graph.invoke(initial_state, config=config)
            return self._build_response(final_state)
        except Exception as exc:
            log_error("start_v2", str(exc), complaint_id)
            return {
                "complaint_id": complaint_id,
                "session_id": session_id,
                "method": input_data.method,
                "status": "error",
                "phase": "error",
                "message": "RCA v2 could not be started.",
                "next_action": None,
                "awaiting_human_review": False,
                "hitl_type": None,
                "ai_flagged": False,
                "stopping_reason": "start_exception",
                "error": f"Start failed: {exc}",
                "root_cause": None,
                "fishbone": {},
                "why": {},
                "timeline": [],
                "node_log": [],
                "audit_log": [],
                "updated_at": time.time(),
                "execution_time_seconds": 0.0,
            }

    def resume_fishbone_selection_v2(self, input_data: RCAFishboneSelectionInputV2) -> Dict[str, Any]:
        try:
            config = {"configurable": {"thread_id": input_data.session_id}}
            self.graph.update_state(config, {"fishbone_selected_cause_id": input_data.selected_cause_id})
            final_state = self.graph.invoke(None, config=config)
            return self._build_response(final_state)
        except Exception as exc:
            complaint_id = input_data.complaint_id or ""
            log_error("resume_fishbone_selection_v2", str(exc), complaint_id)
            return {
                "complaint_id": complaint_id,
                "session_id": input_data.session_id,
                "status": "error",
                "phase": "error",
                "message": "Could not resume fishbone selection.",
                "next_action": None,
                "awaiting_human_review": False,
                "hitl_type": None,
                "ai_flagged": False,
                "stopping_reason": "fishbone_resume_exception",
                "error": f"Fishbone resume failed: {exc}",
                "root_cause": None,
                "fishbone": {},
                "why": {},
                "timeline": [],
                "node_log": [],
                "audit_log": [],
                "updated_at": time.time(),
                "execution_time_seconds": None,
            }

    def resume_why_decision_v2(self, input_data: RCAWhyDecisionInputV2) -> Dict[str, Any]:
        try:
            config = {"configurable": {"thread_id": input_data.session_id}}
            self.graph.update_state(
                config,
                {
                    "why_selected_cause_id": input_data.selected_cause_id,
                    "why_human_decision": input_data.decision,
                },
            )
            final_state = self.graph.invoke(None, config=config)
            return self._build_response(final_state)
        except Exception as exc:
            complaint_id = input_data.complaint_id or ""
            log_error("resume_why_decision_v2", str(exc), complaint_id)
            return {
                "complaint_id": complaint_id,
                "session_id": input_data.session_id,
                "status": "error",
                "phase": "error",
                "message": "Could not resume Why decision.",
                "next_action": None,
                "awaiting_human_review": False,
                "hitl_type": None,
                "ai_flagged": False,
                "stopping_reason": "why_resume_exception",
                "error": f"Why resume failed: {exc}",
                "root_cause": None,
                "fishbone": {},
                "why": {},
                "timeline": [],
                "node_log": [],
                "audit_log": [],
                "updated_at": time.time(),
                "execution_time_seconds": None,
            }

    def status_v2(self, session_id: str) -> Dict[str, Any]:
        try:
            config = {"configurable": {"thread_id": session_id}}
            snapshot = self.graph.get_state(config)
            if snapshot is None or not snapshot.values:
                raise KeyError(f"No RCA v2 session found for '{session_id}'")
            return self._build_response(snapshot.values)
        except KeyError:
            raise
        except Exception as exc:
            log_error("status_v2", str(exc))
            raise KeyError(f"Could not retrieve RCA v2 session for '{session_id}': {exc}") from exc

    @staticmethod
    def _build_response(state: Dict[str, Any]) -> Dict[str, Any]:
        if state.get("final_output"):
            return deep_serialize(state["final_output"])

        return {
            "complaint_id": state.get("complaint_id", ""),
            "session_id": state.get("session_id", ""),
            "method": state.get("method"),
            "status": state.get("status", "running"),
            "phase": state.get("phase", "running"),
            "message": state.get("message"),
            "next_action": state.get("next_action"),
            "awaiting_human_review": bool(state.get("awaiting_human_review", False)),
            "hitl_type": state.get("hitl_type"),
            "ai_flagged": bool(state.get("ai_flagged", False)),
            "stopping_reason": state.get("stopping_reason"),
            "error": state.get("error"),
            "root_cause": deep_serialize(state.get("final_root_cause")),
            "fishbone": {
                "all_causes": deep_serialize(state.get("fishbone_all_causes") or []),
                "categorized_causes": deep_serialize(state.get("fishbone_categorized_causes") or []),
                "validated_causes": deep_serialize(state.get("fishbone_validated_causes") or []),
                "qualified_causes": deep_serialize(state.get("fishbone_qualified_causes") or []),
                "candidate_causes": deep_serialize(state.get("fishbone_candidate_causes") or []),
                "category_summary": deep_serialize(state.get("fishbone_category_summary") or {}),
                "recommended_cause_id": state.get("fishbone_recommended_cause_id"),
                "selected_cause_id": state.get("fishbone_selected_cause_id"),
                "zero_evidence_result": deep_serialize(state.get("fishbone_zero_evidence_result")),
            },
            "why": {
                "depth": int(state.get("why_depth") or 0),
                "current_question": state.get("current_why_question"),
                "current_causes": deep_serialize(state.get("why_current_causes") or []),
                "validated_causes": deep_serialize(state.get("why_validated_causes") or []),
                "qualified_causes": deep_serialize(state.get("why_qualified_causes") or []),
                "candidate_causes": deep_serialize(state.get("why_candidate_causes") or []),
                "why_chain": deep_serialize(state.get("why_chain") or []),
                "iterations": deep_serialize(state.get("why_iterations") or []),
            },
            "agent_payloads": {
                "fishbone": {
                    "cause_generation_input": deep_serialize(state.get("fishbone_cause_generation_input")),
                    "cause_generation_output": deep_serialize(state.get("fishbone_cause_generation_output")),
                    "categorize_input": deep_serialize(state.get("fishbone_categorize_input")),
                    "categorize_output": deep_serialize(state.get("fishbone_categorize_output")),
                    "validation_input": deep_serialize(state.get("fishbone_validation_input")),
                    "validation_output": deep_serialize(state.get("fishbone_validation_output")),
                    "zero_evidence_input": deep_serialize(state.get("fishbone_zero_evidence_input")),
                    "zero_evidence_output": deep_serialize(state.get("fishbone_zero_evidence_output")),
                },
                "why": {
                    "question_start_input": deep_serialize(state.get("why_question_start_input")),
                    "question_continue_input": deep_serialize(state.get("why_question_continue_input")),
                    "question_output": deep_serialize(state.get("why_question_output")),
                    "cause_generation_input": deep_serialize(state.get("why_cause_generation_input")),
                    "cause_generation_output": deep_serialize(state.get("why_cause_generation_output")),
                    "validation_input": deep_serialize(state.get("why_validation_input")),
                    "validation_output": deep_serialize(state.get("why_validation_output")),
                    "zero_evidence_input": deep_serialize(state.get("why_zero_evidence_input")),
                    "zero_evidence_output": deep_serialize(state.get("why_zero_evidence_output")),
                    "question_calls": deep_serialize(state.get("why_question_calls") or []),
                    "cause_generation_calls": deep_serialize(state.get("why_cause_generation_calls") or []),
                    "validation_calls": deep_serialize(state.get("why_validation_calls") or []),
                    "zero_evidence_calls": deep_serialize(state.get("why_zero_evidence_calls") or []),
                },
            },
            "timeline": deep_serialize(state.get("timeline") or []),
            "node_log": deep_serialize(state.get("node_log") or []),
            "audit_log": deep_serialize(state.get("audit_log") or []),
            "updated_at": float(state.get("updated_at") or time.time()),
            "execution_time_seconds": None,
        }
