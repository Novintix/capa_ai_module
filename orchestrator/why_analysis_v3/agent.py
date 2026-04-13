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
            
            print(f"[RESUME] Session: {session_id}, Selected: {selected_cause_id}, Decision: {decision}")
            
            # Get current state to verify checkpoint exists
            try:
                current_state = self.graph.get_state(config)
                print(f"[RESUME] Current state status: {current_state.values.get('status')}")
                print(f"[RESUME] Current awaiting_human_review: {current_state.values.get('awaiting_human_review')}")
                print(f"[RESUME] Current loop count: {current_state.values.get('current_loop_count')}")
                print(f"[RESUME] Next node to execute: {current_state.next}")
            except Exception as e:
                print(f"[RESUME] Warning: Could not get current state: {e}")
            
            # CRITICAL FIX: When resuming from checkpoint, we MUST use invoke(None)
            # Calling invoke(dict) starts a NEW run and goes through initialize again!
            # First update the state, then invoke with None
            
            print(f"[RESUME] Updating checkpoint with human selection...")
            self.graph.update_state(
                config,
                {
                    "human_selected_cause_id": selected_cause_id,
                    "human_decision": decision,
                },
                as_node="human_review"
            )
            
            # Verify update
            updated = self.graph.get_state(config)
            print(f"[RESUME] After update - human_selected_cause_id: {updated.values.get('human_selected_cause_id')}")
            print(f"[RESUME] After update - current_loop_count: {updated.values.get('current_loop_count')}")
            
            # Now invoke with None to continue from checkpoint
            print(f"[RESUME] Invoking with None to continue from checkpoint...")
            final_state = self.graph.invoke(None, config=config)
            
            print(f"[RESUME] Final state status: {final_state.get('status')}")
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
