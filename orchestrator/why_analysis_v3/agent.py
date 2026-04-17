"""
Why Analysis V3 Orchestrator Agent.
Wrapper class for the orchestrator graph.
"""

import time
import uuid
from typing import Dict, Any

from .orchestrator import orchestrator_graph, deep_serialize
from .schemas import WhyAnalysisV3Input
from .logger import log_error


class WhyAnalysisV3Orchestrator:
    """
    Why Analysis V3 Orchestrator Agent.
    
    Simplified flow:
    - question -> causes -> validation -> human_review -> (if 0 causes) zero_evidence
    """

    def __init__(self):
        self.graph = orchestrator_graph

    def analyze(self, input_data: WhyAnalysisV3Input) -> Dict[str, Any]:
        """
        Run Why Analysis V3 orchestration.
        
        Args:
            input_data: WhyAnalysisV3Input with complaint details
            
        Returns:
            Final output dict with results or human review request
        """
        try:
            session_id = input_data.session_id or str(uuid.uuid4())
            
            initial_state = {
                "complaint_id": input_data.complaint_id,
                "complaint": input_data.complaint,
                "evidence": input_data.evidence or "",
                "sop": input_data.sop or "",
                "fmea_document_path": input_data.fmea_document_path,
                "session_id": session_id,
                "evidence_files": input_data.evidence_files,
                "logs": input_data.logs,
                "reports": input_data.reports,
                "process_data": input_data.process_data,
                "historical_capa": input_data.historical_capa,
                "policies": input_data.policies,
                "investigation_records": input_data.investigation_records,
                "supporting_system_information": input_data.supporting_system_information,
                "start_time": time.time(),
                "node_log": [],
                "errors": [],
            }

            config = {"configurable": {"thread_id": session_id}}
            final_state = self.graph.invoke(initial_state, config=config)

            return deep_serialize(final_state.get("final_output") or final_state)

        except Exception as exc:
            log_error("analyze", str(exc))
            return {
                "complaint_id": input_data.complaint_id,
                "session_id": input_data.session_id,
                "status": "error",
                "error": f"Orchestrator error: {exc}",
                "stopping_reason": "orchestrator_exception",
                "ai_flagged": False,
                "manual_investigation_required": True,
                "awaiting_human_review": False,
                "root_cause": None,
                "why_chain": [],
                "iteration_outputs": [],
                "validation_summary": {},
                "execution_time_seconds": 0.0,
                "node_log": [],
                "errors": [{"error": str(exc), "timestamp": time.time()}],
            }

    def resume_with_human_selection(self, session_id: str, selected_cause_id: str, decision: str = "root_cause") -> Dict[str, Any]:
        """
        Resume a paused workflow with human's cause selection.
        
        Args:
            session_id: Session ID to resume
            selected_cause_id: ID of the cause selected by human
            decision: Human decision - "root_cause" (end analysis) or "continue" (dig deeper)
            
        Returns:
            Final output dict with results or next iteration request
        """
        try:
            config = {"configurable": {"thread_id": session_id}}
            
            # Update state with human selection and decision
            update_state = {
                "human_selected_cause_id": selected_cause_id,
                "human_decision": decision,
            }

            self.graph.update_state(config, update_state)
            final_state = self.graph.invoke(None, config=config)
            return deep_serialize(final_state.get("final_output") or final_state)

        except Exception as exc:
            log_error("resume_with_human_selection", str(exc))
            return {
                "session_id": session_id,
                "status": "error",
                "error": f"Resume error: {exc}",
                "stopping_reason": "resume_exception",
                "ai_flagged": False,
                "manual_investigation_required": True,
                "awaiting_human_review": False,
                "root_cause": None,
                "why_chain": [],
                "iteration_outputs": [],
                "validation_summary": {},
                "execution_time_seconds": 0.0,
                "node_log": [],
                "errors": [{"error": str(exc), "timestamp": time.time()}],
            }
