"""
Python entrypoint for Why Analysis V2 orchestrator.
"""

import time
import uuid
from typing import Any, Dict

from .logger import log_error, log_orchestrator_complete, log_orchestrator_start
from .orchestrator import deep_serialize, orchestrator_graph
from .schemas import WhyAnalysisV2Input


class WhyAnalysisV2Orchestrator:
    """Thin Python API around the LangGraph orchestrator."""

    def analyze(self, input_data: WhyAnalysisV2Input) -> Dict[str, Any]:
        start_time = time.time()

        mode = "FMEA_ITERATIVE" if input_data.fmea_document_path else "NO_FMEA_SINGLE_SHOT"
        log_orchestrator_start(input_data.complaint_id, mode, input_data.max_loops or 10)

        session_id = input_data.session_id or f"why-{uuid.uuid4().hex[:12]}"
        config = {"configurable": {"thread_id": session_id}}

        initial_state = {
            **input_data.model_dump(),
            "session_id": session_id,
            "start_time": start_time,
            "status": "running",
            "error": None,
            "next_step": "initialize",
            "node_log": [],
            "errors": [],
        }

        try:
            result = orchestrator_graph.invoke(initial_state, config=config)
            output = result.get("final_output")

            if not output:
                output = {
                    "complaint_id": input_data.complaint_id,
                    "session_id": session_id,
                    "status": "error",
                    "mode": mode,
                    "analysis_depth": 0,
                    "max_loops": input_data.max_loops or 10,
                    "ai_flagged": False,
                    "manual_investigation_required": False,
                    "stopping_reason": "missing_final_output",
                    "root_cause": None,
                    "why_chain": [],
                    "validation_summary": {},
                    "loop_control_summary": {},
                    "execution_time_seconds": round(time.time() - start_time, 4),
                    "error": "Orchestrator finished without final output",
                }

            output = deep_serialize(output)
            log_orchestrator_complete(
                input_data.complaint_id,
                output.get("status", "error"),
                output.get("analysis_depth", 0),
                output.get("execution_time_seconds", round(time.time() - start_time, 4)),
            )
            return output

        except Exception as exc:
            message = f"Why Analysis V2 execution failed: {exc}"
            log_error("analyze", message)
            return {
                "complaint_id": input_data.complaint_id,
                "session_id": session_id,
                "status": "error",
                "mode": mode,
                "analysis_depth": 0,
                "max_loops": input_data.max_loops or 10,
                "ai_flagged": False,
                "manual_investigation_required": False,
                "stopping_reason": "orchestrator_exception",
                "root_cause": None,
                "why_chain": [],
                "validation_summary": {},
                "loop_control_summary": {},
                "execution_time_seconds": round(time.time() - start_time, 4),
                "error": message,
            }
