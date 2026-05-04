"""
Fishbone v3 Orchestrator Agent
Production-grade HITL (Human-in-the-Loop) Fishbone Analysis

Note: This agent can be used standalone or integrated with LangGraph.
For LangGraph integration, see graph.py and nodes.py which provide
a state-machine based workflow with the same logic.
"""

import time
import os
import datetime
from typing import Dict, Any, List, Optional
from .schemas import FishboneV3Input, FishboneV3Output, FishboneV3DecisionInput, DecisionAction
from .logger import (
    log_error, log_orchestrator_start, log_orchestrator_complete,
    log_state_transition, log_agent_call, log_hitl_action
)
from .state_machine import FishboneV3StateMachine, FishboneV3State, IterationMemory, StopReason
from .session_memory import SessionMemoryManagerV3
from agent_ops import agentops_agent, agentops_operation

# Import agents (re-using V2 agent logic)
from Agents.cause_generation.schemas import QuestionInput
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.categorize.graph import categorize_graph
from Agents.categorize.state import CategorizeState, CategorizeInput, Cause
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import ValidationInput, GeneratedCause
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput, CauseInput as ZeroEvidenceCauseInput

try:
    from config.redis_config import (
        _NODE_LABELS,
        get_redis_client,
        publish_agent_event,
        write_agent_status,
    )
except Exception:
    _NODE_LABELS = {}

    def write_agent_status(*args, **kwargs):
        return None

    def publish_agent_event(*args, **kwargs):
        return None

    def get_redis_client():
        return None


@agentops_agent(name="fishbone")
class FishboneOrchestratorV3:
    """
    Fishbone v3 Orchestrator - HITL Flow
    
    1. analyze() -> Runs List Causes, Categorize, Validate. Saves to Redis. Returns WAIT_FOR_HUMAN.
    2. submit_decisions() -> Takes human input (RCA/PROCEED), updates state, completes analysis.
    """
    
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    
    def __init__(self, redis_url: str = None):
        self.cause_agent = CauseGenerationAgent()
        self.validation_agent = ValidationAgent()
        self.zero_evidence_agent = ZeroEvidenceAgent()
        
        # Session memory manager
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.session_manager = SessionMemoryManagerV3(redis_url=redis_url)

    def _session_id(self, complaint_id: str, explicit_session_id: Optional[str] = None) -> str:
        if explicit_session_id:
            return str(explicit_session_id).strip()
        return str(complaint_id).strip()

    def _timestamp(self) -> str:
        return datetime.datetime.utcnow().isoformat() + "Z"

    def _clear_status(self, session_id: str) -> None:
        client = get_redis_client()
        if client is None:
            return
        try:
            client.delete(f"agent_status:{session_id}")
        except Exception:
            pass

    def _emit_node_start(self, session_id: str, node: str) -> None:
        write_agent_status(session_id, node, "running")
        publish_agent_event(
            session_id,
            {
                "type": "node_start",
                "node": node,
                "label": _NODE_LABELS.get(node, node),
                "ts": self._timestamp(),
            },
        )

    def _emit_node_end(self, session_id: str, node: str, output_preview: Optional[str] = None) -> None:
        write_agent_status(session_id, node, "done")
        event = {
            "type": "node_end",
            "node": node,
            "label": _NODE_LABELS.get(node, node),
            "ts": self._timestamp(),
        }
        if output_preview:
            event["output_preview"] = output_preview
        publish_agent_event(session_id, event)

    def _emit_node_error(self, session_id: str, node: str, message: str) -> None:
        write_agent_status(session_id, node, "error")
        publish_agent_event(
            session_id,
            {
                "type": "node_error",
                "node": node,
                "label": _NODE_LABELS.get(node, node),
                "message": message,
                "ts": self._timestamp(),
            },
        )

    def _preview(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip().replace("\n", " ")
        if len(text) <= 140:
            return text
        return text[:137] + "..."
    
    @agentops_operation(name="fishbone")
    def analyze(self, input_data: FishboneV3Input) -> Dict[str, Any]:
        """Phase 1: Run analysis up to validation and wait for human"""
        session_id = self._session_id(input_data.complaint_id, input_data.session_id)
        try:
            self._clear_status(session_id)

            # ── Guardrail: Input Validation ──────────────────────────────────
            self._emit_node_start(session_id, "initialize")
            error = self._validate_input(input_data)
            if error:
                self._emit_node_error(session_id, "initialize", error)
                return {"error": error, "status": "ERROR"}
            self._emit_node_end(session_id, "initialize", "Input validated")

            log_orchestrator_start(input_data.complaint_id, "HITL_V3")
            
            # Initialize state machine
            input_dict = input_data.model_dump()
            state_machine = FishboneV3StateMachine(
                complaint_id=input_dict.pop("complaint_id"),
                complaint=input_dict.pop("complaint"),
                **input_dict
            )
            
            # Step 1: List Causes
            state_machine.transition_to(FishboneV3State.LISTING_CAUSES, "Starting analysis")
            causes_result = self._call_list_causes_agent(state_machine)
            if not causes_result.get("causes"):
                state_machine.control_memory.stop_reason = StopReason.NO_CAUSES_FOUND
                state_machine.transition_to(FishboneV3State.ERROR, "No causes found")
                self._emit_node_start(session_id, "finalize")
                self._emit_node_end(session_id, "finalize", "No causes found")
                return state_machine.get_final_result()
            
            # Step 2: Categorize
            state_machine.transition_to(FishboneV3State.CATEGORIZING, "Causes found")
            categorization_result = self._call_categorization_agent(state_machine, causes_result["causes"])
            
            # ── Guardrail: Sanitize Categorization ───────────────────────────
            self._sanitize_categorization(categorization_result["categorized_causes"])

            # Step 3: Validate
            state_machine.transition_to(FishboneV3State.VALIDATING, "Categorization complete")
            validation_result = self._call_validation_agent(state_machine, categorization_result["categorized_causes"])
            
            # ── Guardrail: Sanitize Validation ───────────────────────────────
            self._sanitize_validation(validation_result["all_causes"])

            # Filter causes with validation_confidence >= 0.9 AND "matched" status only for human review
            high_confidence_causes = [
                c for c in validation_result["all_causes"] 
                if c.get("validation_confidence", 0.0) >= 0.9 
                and c.get("validation_status") == "matched"
            ]
            
            # Log filtering for debugging
            log_agent_call("FilterHighConfidence", {
                "total_causes": len(validation_result["all_causes"]),
                "high_confidence_count": len(high_confidence_causes),
                "criteria": "confidence>=0.9 AND status==matched"
            }, True)
            
            # Save iteration memory
            state_machine.execution_memory.iteration = IterationMemory(
                causes_found=causes_result["causes"],
                categorized_causes=validation_result["all_causes"],
                validated_causes=validation_result["validated_causes"],
                category_summary=categorization_result["category_summary"],
                validation_confidence=validation_result.get("overall_confidence", 0.0)
            )
            
            # Decision logic based on confidence
            if high_confidence_causes:
                # Pause flow for HITL
                state_machine.transition_to(FishboneV3State.WAIT_FOR_HUMAN, "Pausing for human review")
                state_machine.control_memory.stop_reason = StopReason.HITL_PENDING
                self._emit_node_start(session_id, "human_review")
                self._emit_node_end(
                    session_id,
                    "human_review",
                    f"Awaiting review for {len(high_confidence_causes)} causes",
                )
            else:
                # No high confidence causes - use Zero Evidence Agent to rank
                state_machine.transition_to(FishboneV3State.ANALYSIS_COMPLETE, "No high confidence causes - ranking with Zero Evidence Agent")
                state_machine.control_memory.stop_reason = StopReason.COMPLETED
                
                # Call Zero Evidence Agent to rank low confidence causes
                ranked_result = self._call_zero_evidence_agent(state_machine, validation_result["all_causes"])
                state_machine.execution_memory.iteration.categorized_causes = ranked_result.get("ranked_causes", validation_result["all_causes"])
                
                # Store Zero Evidence Agent result separately
                state_machine.execution_memory.iteration.zero_evidence_result = {
                    "selected_root_cause": ranked_result.get("selected_root_cause"),
                    "ranked_causes": ranked_result.get("ranked_causes", []),
                    "total_ranked": len(ranked_result.get("ranked_causes", []))
                }
            
            # Persist full state to Redis
            self._emit_node_start(session_id, "finalize")
            result = state_machine.get_final_result()
            self._emit_node_end(session_id, "finalize", self._preview(result.get("status")))
            
            # Store all causes in Redis for later use
            if high_confidence_causes:
                self.session_manager.save_state(input_data.complaint_id, {
                    "input": input_data.model_dump(),
                    "result": result,
                    "all_causes": validation_result["all_causes"],
                    "execution_trace": state_machine.control_memory.execution_trace
                })
            
            return result
            
        except Exception as e:
            self._emit_node_error(session_id, "finalize", str(e))
            log_error("analyze", str(e))
            return {"error": f"Orchestrator error in analyze: {str(e)}", "status": "ERROR"}

    @agentops_operation(name="submit_decisions")
    def submit_decisions(self, decision_input: FishboneV3DecisionInput) -> Dict[str, Any]:
        """Phase 2: Record human decisions and complete analysis"""
        session_id = self._session_id(decision_input.complaint_id)
        try:
            # 1. Retrieve state from Redis
            state_data = self.session_manager.get_state(decision_input.complaint_id)
            if not state_data:
                return {
                    "error": f"Session expired or not found for {decision_input.complaint_id}. Please call /analyze first.", 
                    "status": "ERROR"
                }

            # Idempotency: if already completed, return persisted final result
            if state_data.get("completed"):
                completed_result = state_data.get("result")
                if completed_result:
                    return completed_result
                return {
                    "error": f"Session {decision_input.complaint_id} is already completed but final result is missing.",
                    "status": "ERROR",
                }
            
            # 2. Re-initialize state machine from persisted data
            input_data = state_data["input"]
            cached_result = state_data["result"]
            all_causes = state_data.get("all_causes", cached_result["causes"])  # Get all causes including low confidence ones
            
            input_data_copy = dict(input_data)
            state_machine = FishboneV3StateMachine(
                complaint_id=input_data_copy.pop("complaint_id"),
                complaint=input_data_copy.pop("complaint"),
                **input_data_copy
            )
            state_machine.execution_memory.iteration = IterationMemory(
                causes_found=[], # Not strictly needed for result generation
                categorized_causes=all_causes,  # Use all causes
                validated_causes=[], # Will be derived below
                category_summary=cached_result["category_summary"]
            )
            state_machine.control_memory.current_state = FishboneV3State.WAIT_FOR_HUMAN
            state_machine.control_memory.execution_trace = state_data.get("execution_trace", [])
            
            # ── Guardrail: Validate Decisions ────────────────────────────────
            valid_cause_ids = {c["cause_id"] for c in cached_result["causes"]}
            decision_error = self._validate_decisions(decision_input, valid_cause_ids)
            if decision_error:
                return {"error": decision_error, "status": "ERROR"}

            self._emit_node_start(session_id, "record_decisions")
            state_machine.transition_to(FishboneV3State.RECORDING_DECISIONS, "User submitted decisions")
            
            # 3. Apply decisions to causes
            decisions_dict = {d.cause_id: d for d in decision_input.decisions}
            for cause in state_machine.execution_memory.iteration.categorized_causes:
                cid = cause.get("cause_id")
                if cid in decisions_dict:
                    decision = decisions_dict[cid]
                    cause["human_decision"] = decision.action
                    cause["human_comment"] = decision.comment
            
            # 4. Finalize
            state_machine.transition_to(FishboneV3State.ANALYSIS_COMPLETE, "Decisions recorded")
            state_machine.control_memory.stop_reason = StopReason.HITL_COMPLETE
            
            log_hitl_action(decision_input.complaint_id, len(cached_result["causes"]), len(decision_input.decisions))
            
            final_result = state_machine.get_final_result()
            self._emit_node_end(
                session_id,
                "record_decisions",
                f"Recorded {len(decision_input.decisions)} decisions",
            )
            self._emit_node_start(session_id, "finalize")

            # Persist terminal completion marker so parent orchestrators can verify child completion.
            self.session_manager.save_state(
                decision_input.complaint_id,
                {
                    **state_data,
                    "completed": True,
                    "status": "COMPLETED",
                    "result": final_result,
                    "completed_at": time.time(),
                },
            )
            self._emit_node_end(session_id, "finalize", self._preview(final_result.get("status")))
            
            log_orchestrator_complete(decision_input.complaint_id, "COMPLETED", final_result["execution_time_seconds"])
            
            return final_result
            
        except Exception as e:
            self._emit_node_error(session_id, "record_decisions", str(e))
            log_error("submit_decisions", str(e))
            return {"error": f"Orchestrator error in submit_decisions: {str(e)}", "status": "ERROR"}

    # ── Guardrail Methods ──────────────────────────────────────────────────────

    def _validate_input(self, input_data: FishboneV3Input) -> Optional[str]:
        """Validate input data to prevent resource issues or hallucinations"""
        if not input_data.complaint or len(input_data.complaint.strip()) < 10:
            return "Invalid complaint: Description must be at least 10 characters long."
        
        if not input_data.complaint_id or not input_data.complaint_id.strip():
            return "Invalid complaint_id: Must not be empty."
        
        return None

    def _validate_decisions(self, decision_input: FishboneV3DecisionInput, valid_cause_ids: set) -> Optional[str]:
        """Ensure decisions refer to actual causes found in Phase 1"""
        if not decision_input.decisions:
            return "Invalid request: Decisions list cannot be empty."

        for dec in decision_input.decisions:
            if dec.cause_id not in valid_cause_ids:
                return f"Integrity error: Cause ID '{dec.cause_id}' was not found in the original analysis results."
        
        return None

    def _sanitize_categorization(self, causes: List[Dict]):
        """Ensure categories and confidence scores are within valid bounds"""
        valid_cats = {"Man", "Machine", "Method", "Material", "Measurement", "Environment", "Unknown"}
        for cause in causes:
            # Force valid category
            orig_cat = cause.get("category", "Unknown")
            if orig_cat not in valid_cats:
                cause["category"] = "Unknown"
                cause["category_reasoning"] = f"Original category '{orig_cat}' was invalid; defaulted to Unknown."
            
            # Clip confidence
            conf = cause.get("category_confidence", 0.0) or 0.0
            cause["category_confidence"] = max(0.0, min(1.0, float(conf)))

    def _sanitize_validation(self, causes: List[Dict]):
        """Sanitize validation output data"""
        for cause in causes:
            conf = cause.get("validation_confidence", 0.0) or 0.0
            cause["validation_confidence"] = max(0.0, min(1.0, float(conf)))
            
            if not cause.get("validation_status"):
                 cause["validation_status"] = "not_matched"

    # ── Internal Agent Call Methods (Adapted from V2) ──────────────────────────
    
    @agentops_operation(name="A13_Cause_Generation_Agent")
    def _call_list_causes_agent(self, state_machine: FishboneV3StateMachine) -> Dict[str, Any]:
        """Generate causes from complaint"""
        session_id = self._session_id(state_machine.complaint_id, state_machine.kwargs.get("session_id"))
        self._emit_node_start(session_id, "list_causes_agent")
        state_machine.control_memory.execution_trace.append("1. ListCausesAgent")
        log_agent_call("ListCausesAgent", {"id": state_machine.complaint_id}, None)
        
        question_input = QuestionInput(
            question_id=f"{state_machine.complaint_id}_v3",
            question=f"What are the potential causes of: {state_machine.complaint}",
            context=state_machine.complaint
        )
        # Use cause generation agent
        result = self.cause_agent.process_question(question_input, state_machine.kwargs.get("fmea_document_path"))
        causes = result.get("causes", [])
        
        log_agent_call("ListCausesAgent", {"found": len(causes)}, True)
        self._emit_node_end(session_id, "list_causes_agent", f"Found {len(causes)} causes")
        return {"causes": causes}

    @agentops_operation(name="A1_Categorize_Agent")
    def _call_categorization_agent(self, state_machine: FishboneV3StateMachine, causes: List[Dict]) -> Dict[str, Any]:
        """Categorize into 6M"""
        session_id = self._session_id(state_machine.complaint_id, state_machine.kwargs.get("session_id"))
        self._emit_node_start(session_id, "categorize_agent")
        state_machine.control_memory.execution_trace.append("2. CategorizationAgent")
        
        categorize_causes = [Cause(cause_id=c["cause_id"], cause_text=c["cause_text"]) for c in causes]
        categorize_input = CategorizeInput(
            question=state_machine.complaint,
            causes=categorize_causes
        )
        
        result = categorize_graph.invoke(CategorizeState(input=categorize_input, iteration=0))
        output = result.get("final_output")
        
        if output:
            cat_map = {c.cause_id: c for c in output.categorized_causes}
            for cause in causes:
                match = cat_map.get(cause["cause_id"])
                if match:
                    cause.update({
                        "category": match.category,
                        "category_confidence": match.confidence,
                        "category_reasoning": match.reasoning
                    })
            self._emit_node_end(session_id, "categorize_agent", f"Categorized {len(causes)} causes")
            return {"categorized_causes": causes, "category_summary": output.summary}
        
        self._emit_node_end(session_id, "categorize_agent", "No category summary returned")
        return {"categorized_causes": causes, "category_summary": {}}

    @agentops_operation(name="A14_Validation_Agent")
    def _call_validation_agent(self, state_machine: FishboneV3StateMachine, causes: List[Dict]) -> Dict[str, Any]:
        """Validate against evidence"""
        session_id = self._session_id(state_machine.complaint_id, state_machine.kwargs.get("session_id"))
        self._emit_node_start(session_id, "validation_agent_v3")
        state_machine.control_memory.execution_trace.append("3. ValidationAgent")
        
        generated = [GeneratedCause(cause_id=c["cause_id"], cause_text=c["cause_text"]) for c in causes]
        v_input = ValidationInput(
            complaint_id=state_machine.complaint_id,
            question=state_machine.complaint,
            generated_causes=generated,
            complaint_description=state_machine.complaint,
            investigation_evidence=state_machine.kwargs.get("evidence", "")
        )
        
        result = self.validation_agent.validate_causes(v_input)
        
        # Use cause_validation_results which contains ALL causes with their validation scores
        val_map = {vc["cause_id"]: vc for vc in result.get("cause_validation_results", [])}
        
        validated_causes = []
        for cause in causes:
            match = val_map.get(cause["cause_id"])
            if match:
                cause.update({
                    "validation_status": match.get("evidence_match_status"),
                    "validation_confidence": match.get("confidence"),
                    "validation_rationale": match.get("rationale")
                })
                # Only add to validated_causes if it has evidence support
                if match.get("evidence_match_status") in ["matched", "partially_matched"]:
                    validated_causes.append(cause)
        
        result_payload = {
            "all_causes": causes,
            "validated_causes": validated_causes,
            "overall_confidence": result.get("overall_confidence", 0.0)
        }
        self._emit_node_end(
            session_id,
            "validation_agent_v3",
            f"Validated {len(validated_causes)} of {len(causes)} causes",
        )
        return result_payload

    @agentops_operation(name="A17_Zero_Evidence_Agent")
    def _call_zero_evidence_agent(self, state_machine: FishboneV3StateMachine, causes: List[Dict]) -> Dict[str, Any]:
        """Rank causes using Zero Evidence Agent when no high confidence causes exist"""
        session_id = self._session_id(state_machine.complaint_id, state_machine.kwargs.get("session_id"))
        self._emit_node_start(session_id, "zero_evidence_agent")
        state_machine.control_memory.execution_trace.append("4. ZeroEvidenceAgent (Ranking)")
        log_agent_call("ZeroEvidenceAgent", {"causes": len(causes)}, None)
        
        try:
            # Convert causes to ZeroEvidenceCauseInput format
            zero_evidence_causes = [
                ZeroEvidenceCauseInput(
                    cause_id=c["cause_id"],
                    cause_text=c["cause_text"],
                    process_step=c.get("process_step"),
                    failure_mode=c.get("failure_mode"),
                    potential_effects=c.get("potential_effects"),
                    category=c.get("category", "Unknown"),
                    severity=c.get("severity", 5),
                    occurrence=c.get("occurrence", 5),
                    detection=c.get("detection", 5),
                    current_controls=c.get("current_controls"),
                    source=c.get("source", "FMEA")
                ) for c in causes
            ]
            
            zero_input = ZeroEvidenceInput(
                question_id=state_machine.complaint_id,
                complaint_id=state_machine.complaint_id,
                question=state_machine.complaint,
                causes=zero_evidence_causes,
                complaint_description=state_machine.complaint,
                investigation_evidence=state_machine.kwargs.get("evidence", ""),
                total_causes=len(zero_evidence_causes)
            )
            
            result = self.zero_evidence_agent.analyze(zero_input)
            
            # Update causes with ranking information
            selected_root = result.get("selected_root_cause")
            if selected_root:
                for cause in causes:
                    if cause["cause_id"] == selected_root.get("cause_id"):
                        cause["zero_evidence_rank"] = 1
                        cause["zero_evidence_score"] = result.get("confidence", 0.0)
                        cause["zero_evidence_reasoning"] = selected_root.get("reason", "")
                        break
            
            log_agent_call("ZeroEvidenceAgent", {"selected": selected_root is not None}, True)
            self._emit_node_end(
                session_id,
                "zero_evidence_agent",
                self._preview(selected_root.get("cause_text") if selected_root else "No root cause ranked"),
            )
            
            return {
                "ranked_causes": causes,
                "selected_root_cause": result.get("selected_root_cause")
            }
        
        except Exception as e:
            self._emit_node_error(session_id, "zero_evidence_agent", str(e))
            log_error("_call_zero_evidence_agent", str(e))
            return {"ranked_causes": causes, "selected_root_cause": None}
