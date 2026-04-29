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
from agent_ops import agentops_agent, agentops_operation


@agentops_agent(name="Why_Analysis_Orchestrator")
class WhyAnalysisV3Orchestrator:
    """
    Why Analysis V3 Orchestrator Agent.
    
    Simplified flow:
    - question -> causes -> validation -> human_review -> (if 0 causes) zero_evidence
    """

    def __init__(self):
        self.graph = orchestrator_graph

    @agentops_operation(name="Why_Analysis_Workflow")
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
                "mode": "NO_FMEA_SINGLE_SHOT",  # Required field
                "analysis_depth": 0,  # Required field
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

    @agentops_operation(name="resume_with_human_selection")
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
            
            print(f"\n{'='*80}")
            print(f"[RESUME] Starting resume process")
            print(f"[RESUME] Session: {session_id}")
            print(f"[RESUME] Selected: {selected_cause_id}")
            print(f"[RESUME] Decision: {decision}")
            print(f"{'='*80}\n")
            
            # Get current state to verify checkpoint exists
            try:
                current_state = self.graph.get_state(config)
                print(f"[RESUME] ✓ Checkpoint found")
                print(f"[RESUME]   - Status: {current_state.values.get('status')}")
                print(f"[RESUME]   - Awaiting review: {current_state.values.get('awaiting_human_review')}")
                print(f"[RESUME]   - Loop count: {current_state.values.get('current_loop_count')}")
                print(f"[RESUME]   - Complaint ID: {current_state.values.get('complaint_id')}")
                print(f"[RESUME]   - Next nodes: {current_state.next}")
                
                # Verify we have a valid checkpoint
                if not current_state.values or not current_state.values.get('complaint_id'):
                    raise Exception("Checkpoint exists but has no valid state data")
                    
            except Exception as e:
                print(f"[RESUME] ✗ ERROR: Could not load checkpoint: {e}")
                return {
                    "session_id": session_id,
                    "status": "error",
                    "error": f"No valid checkpoint found for session {session_id}: {e}",
                    "stopping_reason": "no_checkpoint",
                    "mode": "NO_FMEA_SINGLE_SHOT",  # Required field
                    "analysis_depth": 0,  # Required field
                }
            
            # CRITICAL FIX: The issue is that invoke(None) doesn't work at END interrupt
            # We need to manually call human_review_node with the updated state
            # Then continue the graph execution
            
            print(f"\n[RESUME] Step 1: Manually processing human selection...")
            
            # Get the current state values
            state_values = dict(current_state.values)
            
            # Add human selection
            state_values["human_selected_cause_id"] = selected_cause_id
            state_values["human_decision"] = decision
            
            # Manually call human_review_node to process the selection
            from .orchestrator import human_review_node
            print(f"[RESUME] Step 2: Calling human_review_node with selection...")
            updated_state = human_review_node(state_values)
            
            # Merge the updated state
            for key, value in updated_state.items():
                state_values[key] = value
            
            print(f"[RESUME] Step 3: Updated state:")
            print(f"[RESUME]   - Status: {state_values.get('status')}")
            print(f"[RESUME]   - Awaiting review: {state_values.get('awaiting_human_review')}")
            print(f"[RESUME]   - current_selected_cause exists: {bool(state_values.get('current_selected_cause'))}")
            
            # Check if we need to continue or finalize
            if state_values.get("status") == "completed":
                # Human selected root cause - finalize
                print(f"[RESUME] Step 4: Finalizing (root cause selected)...")
                from .orchestrator import finalize_node
                final_update = finalize_node(state_values)
                for key, value in final_update.items():
                    state_values[key] = value
                
                print(f"\n[RESUME] ✓ Resume complete (finalized)")
                print(f"[RESUME]   - Final status: {state_values.get('status')}")
                print(f"{'='*80}\n")
                
                return deep_serialize(state_values.get("final_output") or state_values)
            
            elif state_values.get("status") == "running" and state_values.get("current_selected_cause"):
                # Human chose to continue - need to run next iteration
                print(f"[RESUME] Step 4: Continuing to next iteration...")
                
                # Update the checkpoint with new state
                self.graph.update_state(config, state_values, as_node="human_review")
                
                # Now invoke to continue the workflow
                print(f"[RESUME] Step 5: Invoking graph for next iteration...")
                final_state = self.graph.invoke(None, config=config)
                
                print(f"\n[RESUME] ✓ Resume complete (next iteration)")
                print(f"[RESUME]   - Final status: {final_state.get('status')}")
                print(f"[RESUME]   - Awaiting review: {final_state.get('awaiting_human_review')}")
                print(f"{'='*80}\n")
                
                return deep_serialize(final_state.get("final_output") or final_state)
            
            else:
                # Something unexpected
                print(f"[RESUME] ✗ Unexpected state after human_review_node")
                print(f"[RESUME]   - Status: {state_values.get('status')}")
                print(f"[RESUME]   - Has selected cause: {bool(state_values.get('current_selected_cause'))}")
                
                return deep_serialize(state_values.get("final_output") or state_values)

        except Exception as exc:
            log_error("resume_with_human_selection", str(exc))
            return {
                "session_id": session_id,
                "status": "error",
                "mode": "NO_FMEA_SINGLE_SHOT",  # Required field
                "analysis_depth": 0,  # Required field
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
