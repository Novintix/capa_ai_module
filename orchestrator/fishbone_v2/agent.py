"""
Fishbone v2 Orchestrator Agent
Production-grade single-depth fishbone analysis with 6M categorization

Flow: Complaint → List Causes → Categorize → Validate → Route Decision
  - No evidence matched → Zero Evidence Agent
  - 1 cause matched → Select and complete
  - >1 causes matched → Ranking Agent
"""

import time
import os
from typing import Dict, Any, List, Optional
from .schemas import FishboneInput, FishboneOutput
from .logger import (
    log_error, log_orchestrator_start, log_orchestrator_complete,
    log_state_transition, log_memory_update, log_agent_call, log_routing_decision
)
from .state_machine import FishboneStateMachine, FishboneState, IterationMemory, StopReason
from .session_memory import SessionMemoryManager, SessionState

# Import agents
from Agents.cause_generation.schemas import QuestionInput
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.categorize.graph import categorize_graph
from Agents.categorize.state import CategorizeState, CategorizeInput, Cause
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import ValidationInput, GeneratedCause
from Agents.ranking.agent import RankingAgent
from Agents.ranking.state import CauseInput as RankingCauseInput
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput, CauseInput as ZeroEvidenceCauseInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent


class FishboneOrchestratorV2:
    """
    Production-grade Fishbone v2 Orchestrator - Single Depth Analysis
    
    Flow:
    1. List Causes Agent → Generate causes from complaint description
    2. Categorization Agent → Classify into 6M categories
    3. Validation Agent → Validate against evidence
    4. Decision Router:
       - 0 validated causes → Zero Evidence Agent (select & stop)
       - 1 validated cause → Select it and stop
       - >1 validated causes → Ranking Agent (select & stop)
    
    Features:
    - Single depth analysis (no iteration loops)
    - Redis session management
    - 6M categorization (Man, Machine, Method, Material, Measurement, Environment)
    - Evidence-based validation
    - Confidence-based routing
    - Production-grade error handling
    """
    
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    
    def __init__(self, redis_url: str = None):
        """Initialize all agents and session memory"""
        self.cause_agent = CauseGenerationAgent()
        self.validation_agent = ValidationAgent()
        self.ranking_agent = RankingAgent()
        self.zero_evidence_agent = ZeroEvidenceAgent()
        
        # Session memory manager
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.session_manager = SessionMemoryManager(redis_url=redis_url)
    
    def analyze(self, input_data: FishboneInput) -> Dict[str, Any]:
        """
        Run complete Fishbone v2 Analysis - Single Depth
        
        Args:
            input_data: Input with complaint and optional FMEA
            
        Returns:
            Complete analysis result with 6M categorization
        """
        try:
            # Input validation
            validation_error = self._validate_input(input_data)
            if validation_error:
                return self._create_validation_error_response(input_data, validation_error)
            
            log_orchestrator_start(input_data.complaint_id, "SINGLE_SHOT", 1)
            
            # Get or create session
            session = self.session_manager.get_session(input_data.complaint_id)
            
            if session and session.is_complete:
                # Session already complete - return cached result
                log_memory_update(
                    "orchestrator",
                    input_data.complaint_id,
                    "session_complete",
                    "Session already complete, returning cached result"
                )
                return self._build_result_from_session(session)
            
            # Create new session
            if not session:
                session = self.session_manager.create_session(
                    complaint_id=input_data.complaint_id,
                    complaint=input_data.complaint,
                    evidence=input_data.evidence or "",
                    sop=input_data.sop or "",
                    fmea_document_path=input_data.fmea_document_path
                )
            
            # Initialize state machine
            state_machine = FishboneStateMachine(
                complaint_id=input_data.complaint_id,
                complaint=input_data.complaint,
                evidence=input_data.evidence or "",
                sop=input_data.sop or "",
                fmea_document_path=input_data.fmea_document_path,
                evidence_files=input_data.evidence_files or [],
                logs=input_data.logs,
                reports=input_data.reports,
                process_data=input_data.process_data,
                historical_capa=input_data.historical_capa,
                policies=input_data.policies,
                investigation_records=input_data.investigation_records,
                supporting_system_information=input_data.supporting_system_information
            )
            
            # Execute single iteration
            state_machine.start_iteration()
            success = self._execute_single_iteration(state_machine, session)
            
            if not success:
                state_machine.transition_to(FishboneState.ERROR, "Iteration execution failed")
            
            # Mark session complete
            if state_machine.control_memory.final_root_cause:
                root_cause_id = state_machine.control_memory.final_root_cause.get("cause_id", "UNKNOWN")
                self.session_manager.mark_complete(session, root_cause_id)
            
            # Get final result
            result = state_machine.get_final_result()
            
            log_orchestrator_complete(
                input_data.complaint_id,
                1,
                bool(result.get("root_cause")),
                result.get("execution_time_seconds", 0.0)
            )
            
            return result
            
        except Exception as e:
            log_error("analyze", str(e))
            return self._create_error_response(input_data, str(e))
    
    def _execute_single_iteration(self, state_machine: FishboneStateMachine, session: SessionState) -> bool:
        """
        Execute single iteration
        
        Flow: List Causes → Categorize → Validate → Route Decision
        """
        try:
            # ═══════════════════════════════════════════════════════════
            # STEP 1: List Causes Agent (Generate causes from complaint)
            # ═══════════════════════════════════════════════════════════
            causes_result = self._call_list_causes_agent(state_machine)
            
            if not causes_result.get("causes"):
                log_error("_execute_single_iteration", "No causes generated")
                state_machine.control_memory.stop_reason = StopReason.NO_CAUSES_FOUND
                return True
            
            state_machine.transition_to(FishboneState.CATEGORIZING, "Causes generated")
            
            # ═══════════════════════════════════════════════════════════
            # STEP 2: Categorization Agent (6M Categories)
            # ═══════════════════════════════════════════════════════════
            categorization_result = self._call_categorization_agent(
                state_machine,
                causes_result["causes"]
            )
            
            categorized_causes = categorization_result["categorized_causes"]
            category_summary = categorization_result["category_summary"]
            
            state_machine.transition_to(FishboneState.VALIDATING, "Causes categorized")
            
            # ═══════════════════════════════════════════════════════════
            # STEP 3: Validation Agent
            # ═══════════════════════════════════════════════════════════
            validation_result = self._call_validation_agent(state_machine, categorized_causes)
            
            state_machine.transition_to(FishboneState.ROUTING_DECISION, "Validation complete")
            
            # ═══════════════════════════════════════════════════════════
            # STEP 4: Decision Router
            # ═══════════════════════════════════════════════════════════
            num_validated = validation_result["num_validated"]
            high_confidence_count = validation_result["high_confidence_count"]
            
            selected_cause = None
            
            if num_validated == 0:
                # Path: No evidence matched → Zero Evidence Agent
                log_routing_decision("validation", "zero_evidence", "No validated causes")
                state_machine.transition_to(FishboneState.ZERO_EVIDENCE, "No validated causes")
                
                selected_cause = self._call_zero_evidence_for_selection(
                    state_machine,
                    categorized_causes
                )
                
                if selected_cause:
                    selected_cause["selection_justification"] = "No validated causes found. Selected by Zero Evidence agent based on criticality."
                
            elif num_validated == 1:
                # Path: 1 cause matched → Select it and complete
                log_routing_decision("validation", "analysis_complete", "Single validated cause")
                selected_cause = validation_result["validated_causes"][0]
                selected_cause["selection_justification"] = f"Single validated cause with confidence {selected_cause.get('validation_confidence', 0.0):.2f}"
                
            else:
                # Path: >1 causes matched → Ranking Agent
                log_routing_decision("validation", "ranking", f"{num_validated} validated causes")
                state_machine.transition_to(FishboneState.RANKING, "Multiple validated causes")
                
                selected_cause = self._call_ranking_agent(
                    state_machine,
                    validation_result["validated_causes"]
                )
            
            # Guardrail: If no cause selected, use fallback
            if not selected_cause:
                log_error("_execute_single_iteration", "No cause selected - using fallback")
                if validation_result["validated_causes"]:
                    selected_cause = validation_result["validated_causes"][0]
                elif categorized_causes:
                    selected_cause = categorized_causes[0]
                else:
                    return False
                selected_cause["selection_justification"] = "Fallback selection - no cause selected by agents"
            
            # ═══════════════════════════════════════════════════════════
            # SESSION MEMORY: Add iteration to session
            # ═══════════════════════════════════════════════════════════
            self.session_manager.add_iteration(
                session=session,
                causes_evaluated=validation_result["all_causes"],
                selected_cause=selected_cause,
                validation_confidence=validation_result.get("overall_confidence", 0.0)
            )
            
            # Create iteration memory
            iteration = IterationMemory(
                depth=1,
                causes_found=causes_result["causes"],
                categorized_causes=categorized_causes,
                validated_causes=validation_result["validated_causes"],
                selected_cause=selected_cause,
                fmea_matches=causes_result.get("fmea_matches", 0),
                generation_method=causes_result.get("method", "unknown"),
                validation_confidence=validation_result.get("overall_confidence", 0.0),
                high_confidence_count=high_confidence_count,
                category_summary=category_summary,
                selection_justification=selected_cause.get("selection_justification")
            )
            
            # Complete iteration
            state_machine.complete_iteration(iteration)
            
            return True
            
        except Exception as e:
            log_error("_execute_single_iteration", str(e))
            return False

    
    def _call_list_causes_agent(self, state_machine: FishboneStateMachine) -> Dict[str, Any]:
        """
        List Causes Agent - Generate causes directly from complaint description
        Uses Cause Generation Agent with complaint as the "question"
        """
        try:
            state_machine.control_memory.execution_trace.append("1. ListCausesAgent - Started")
            log_agent_call("ListCausesAgent", {"complaint": state_machine.complaint[:100]}, None, None)
            
            # Use complaint description as the question for cause generation
            question_input = QuestionInput(
                question_id=f"{state_machine.complaint_id}_depth1",
                question=f"What are the potential causes of: {state_machine.complaint}",
                context=state_machine.complaint
            )
            
            # Call cause generation agent
            result = self.cause_agent.process_question(
                question_input,
                state_machine.fmea_document_path
            )
            
            causes = result.get("causes", [])
            
            # Fallback to LLM if FMEA returns no causes
            if not causes and state_machine.fmea_document_path:
                log_memory_update(
                    "list_causes",
                    state_machine.complaint_id,
                    "fmea_fallback",
                    "FMEA returned no causes, falling back to LLM generation"
                )
                result = self.cause_agent.process_question(question_input, None)
                causes = result.get("causes", [])
            
            log_agent_call(
                "ListCausesAgent",
                {"causes_found": len(causes), "method": result.get("method", "unknown")},
                True
            )
            
            state_machine.control_memory.execution_trace.append(f"1. ListCausesAgent - Success ({len(causes)} causes, {result.get('method', 'unknown')})")
            
            return {
                "causes": causes,
                "fmea_matches": result.get("matched_entries", 0),
                "method": "FMEA" if result.get("matched_entries", 0) > 0 else "LLM_Generated"
            }
            
        except Exception as e:
            log_error("_call_list_causes_agent", str(e))
            log_agent_call("ListCausesAgent", {}, False, str(e))
            return {"causes": [], "fmea_matches": 0, "method": "error"}
    
    def _call_categorization_agent(self, state_machine: FishboneStateMachine, causes: List[Dict]) -> Dict[str, Any]:
        """
        Categorization Agent - Categorize causes into 6M categories
        Categories: Man, Machine, Method, Material, Measurement, Environment
        """
        try:
            state_machine.control_memory.execution_trace.append("2. CategorizationAgent - Started")
            log_agent_call("CategorizationAgent", {"causes_count": len(causes)}, None, None)
            
            # Convert causes to categorize format
            categorize_causes = []
            for cause in causes:
                categorize_causes.append(Cause(
                    cause_id=cause.get("cause_id", ""),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", ""),
                    failure_mode=cause.get("failure_mode", ""),
                    potential_effects=cause.get("potential_effects", "") or "",
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "")
                ))
            
            # Create categorization input
            categorize_input = CategorizeInput(
                question=f"Categorize causes for: {state_machine.complaint}",
                causes=categorize_causes,
                additional_context=state_machine.complaint
            )
            
            # Call categorization graph
            initial_state = CategorizeState(
                input=categorize_input,
                iteration=0
            )
            
            result = categorize_graph.invoke(initial_state)
            
            # Extract categorized causes
            if result.get("final_output"):
                categorized_causes_list = result["final_output"].categorized_causes
                category_summary = result["final_output"].summary
                
                # Add category to original causes
                categorized_causes = []
                for cause in causes:
                    matching_cat = next(
                        (cat for cat in categorized_causes_list if cat.cause_id == cause.get("cause_id")),
                        None
                    )
                    
                    if matching_cat:
                        cause["category"] = matching_cat.category
                        cause["category_confidence"] = matching_cat.confidence
                        cause["category_reasoning"] = matching_cat.reasoning
                        cause["secondary_categories"] = matching_cat.secondary_categories
                    else:
                        cause["category"] = "Unknown"
                        cause["category_confidence"] = 0.0
                        cause["category_reasoning"] = "Categorization failed"
                        cause["secondary_categories"] = []
                    
                    categorized_causes.append(cause)
                
                log_agent_call(
                    "CategorizationAgent",
                    {"categorized_count": len(categorized_causes), "category_summary": category_summary},
                    True
                )
                
                state_machine.control_memory.execution_trace.append(f"2. CategorizationAgent - Success ({len(categorized_causes)} categorized)")
                
                return {
                    "categorized_causes": categorized_causes,
                    "category_summary": category_summary
                }
            else:
                # Categorization failed
                log_error("_call_categorization_agent", "Categorization graph returned no output")
                for cause in causes:
                    cause["category"] = "Unknown"
                    cause["category_confidence"] = 0.0
                    cause["category_reasoning"] = "Categorization failed"
                    cause["secondary_categories"] = []
                
                return {
                    "categorized_causes": causes,
                    "category_summary": {"Unknown": len(causes)}
                }
                
        except Exception as e:
            log_error("_call_categorization_agent", str(e))
            log_agent_call("CategorizationAgent", {}, False, str(e))
            
            # Return causes without categories on error
            for cause in causes:
                cause["category"] = "Unknown"
                cause["category_confidence"] = 0.0
                cause["category_reasoning"] = f"Error: {str(e)}"
                cause["secondary_categories"] = []
            
            return {
                "categorized_causes": causes,
                "category_summary": {"Unknown": len(causes)}
            }
    
    def _call_validation_agent(self, state_machine: FishboneStateMachine, causes: List[Dict]) -> Dict[str, Any]:
        """
        Validation Agent - Validate causes against evidence
        """
        try:
            state_machine.control_memory.execution_trace.append("3. ValidationAgent - Started")
            log_agent_call("ValidationAgent", {"causes_count": len(causes)}, None, None)
            
            # Prepare causes for validation
            generated_causes = []
            for cause in causes:
                # Ensure potential_effects is a string (not bool/None)
                potential_effects = cause.get("potential_effects")
                if potential_effects is None or isinstance(potential_effects, bool):
                    potential_effects = ""
                
                generated_causes.append(GeneratedCause(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", ""),
                    failure_mode=cause.get("failure_mode", ""),
                    potential_effects=potential_effects,
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "FMEA")
                ))
            
            # Create validation input
            validation_input = ValidationInput(
                complaint_id=state_machine.complaint_id,
                question_id=f"{state_machine.complaint_id}_depth1",
                question=f"Validate causes for: {state_machine.complaint}",
                generated_causes=generated_causes,
                complaint_description=state_machine.complaint,  # REQUIRED field
                evidence=state_machine.evidence,
                sop=state_machine.sop,
                evidence_files=state_machine.evidence_files or [],
                logs=state_machine.logs,
                reports=state_machine.reports,
                process_data=state_machine.process_data,
                historical_capa=state_machine.historical_capa,
                policies=state_machine.policies,
                investigation_records=state_machine.investigation_records,
                supporting_system_information=state_machine.supporting_system_information
            )
            
            # Call validation agent
            result = self.validation_agent.validate_causes(validation_input)
            
            validated_causes_list = result.get("validated_causes", [])
            
            # Add validation fields back to original causes
            all_causes = []
            validated_causes = []
            high_confidence_causes = []
            
            for cause in causes:
                # Find matching validation result
                matching_val = next(
                    (vc for vc in validated_causes_list if vc.get("cause_id") == cause.get("cause_id")),
                    None
                )
                
                if matching_val:
                    # Validation Agent returns "evidence_match_status", not "validation_status"
                    evidence_status = matching_val.get("evidence_match_status", "no_evidence")
                    cause["validation_status"] = evidence_status
                    cause["validation_confidence"] = matching_val.get("confidence", 0.0)
                    cause["validation_rationale"] = matching_val.get("rationale", "")
                    cause["supporting_evidence"] = matching_val.get("supporting_evidence_references", [])
                    
                    # Track validated causes
                    if evidence_status in ["matched", "partially_matched"]:
                        validated_causes.append(cause)
                        
                        # Track high confidence causes
                        if matching_val.get("confidence", 0.0) >= self.HIGH_CONFIDENCE_THRESHOLD:
                            high_confidence_causes.append(cause)
                else:
                    cause["validation_status"] = "not_matched"
                    cause["validation_confidence"] = 0.0
                
                all_causes.append(cause)
            
            log_agent_call(
                "ValidationAgent",
                {
                    "validated": len(validated_causes),
                    "high_confidence": len(high_confidence_causes)
                },
                True
            )
            
            state_machine.control_memory.execution_trace.append(f"3. ValidationAgent - Success ({len(validated_causes)} validated, {len(high_confidence_causes)} high confidence)")
            
            return {
                "num_validated": len(validated_causes),
                "high_confidence_count": len(high_confidence_causes),
                "validated_causes": validated_causes,
                "high_confidence_causes": high_confidence_causes,
                "all_causes": all_causes,
                "overall_confidence": result.get("overall_confidence", 0.0)
            }
            
        except Exception as e:
            log_error("_call_validation_agent", str(e))
            log_agent_call("ValidationAgent", {}, False, str(e))
            
            # Return all causes as unvalidated
            for cause in causes:
                cause["validation_status"] = "error"
                cause["validation_confidence"] = 0.0
            
            return {
                "num_validated": 0,
                "high_confidence_count": 0,
                "validated_causes": [],
                "high_confidence_causes": [],
                "all_causes": causes,
                "overall_confidence": 0.0
            }
    
    def _call_ranking_agent(self, state_machine: FishboneStateMachine, causes: List[Dict]) -> Optional[Dict]:
        """
        Ranking Agent - Rank multiple validated causes
        """
        try:
            state_machine.control_memory.execution_trace.append("4. RankingAgent - Started")
            log_agent_call("RankingAgent", {"causes_count": len(causes)}, None, None)
            
            # Convert to ranking format
            ranking_causes = []
            for cause in causes:
                # Ensure potential_effects is a string
                potential_effects = cause.get("potential_effects")
                if potential_effects is None or isinstance(potential_effects, bool):
                    potential_effects = ""
                
                ranking_causes.append(RankingCauseInput(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", ""),
                    failure_mode=cause.get("failure_mode", ""),
                    potential_effects=potential_effects,
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "FMEA")
                ))
            
            # Call ranking agent
            result = self.ranking_agent.rank_causes(ranking_causes)
            
            if result.get("ranked_causes"):
                top_cause = result["ranked_causes"][0]
                
                # Find original cause to preserve all fields
                selected = next(
                    (c for c in causes if c.get("cause_id") == top_cause.get("cause_id")),
                    top_cause
                )
                
                selected["reason"] = top_cause.get("reason", "Highest RCPS score")
                selected["confidence_score"] = top_cause.get("rcps_score", 0.0) / 10.0
                selected["selection_justification"] = f"Ranked highest by RCPS methodology. {top_cause.get('reason', '')}"
                
                state_machine.control_memory.execution_trace.append(f"4. RankingAgent - Success (selected {selected.get('cause_id')})")
                log_agent_call("RankingAgent", {"selected": selected.get("cause_id")}, True)
                
                return selected
            
            log_error("_call_ranking_agent", "No ranked causes returned")
            return causes[0] if causes else None
            
        except Exception as e:
            log_error("_call_ranking_agent", str(e))
            log_agent_call("RankingAgent", {}, False, str(e))
            return causes[0] if causes else None
    
    def _call_zero_evidence_for_selection(self, state_machine: FishboneStateMachine, causes: List[Dict]) -> Optional[Dict]:
        """
        Zero Evidence Agent - Select from unvalidated causes
        """
        try:
            state_machine.control_memory.execution_trace.append("4. ZeroEvidenceAgent - Started")
            log_agent_call("ZeroEvidenceAgent", {"causes_count": len(causes)}, None, None)
            
            # Convert to zero evidence format
            zero_causes = []
            for cause in causes:
                # Ensure potential_effects is a string
                potential_effects = cause.get("potential_effects")
                if potential_effects is None or isinstance(potential_effects, bool):
                    potential_effects = ""
                
                zero_causes.append(ZeroEvidenceCauseInput(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", ""),
                    failure_mode=cause.get("failure_mode", ""),
                    potential_effects=potential_effects,
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "FMEA")
                ))
            
            zero_input = ZeroEvidenceInput(
                question_id=f"{state_machine.complaint_id}_depth1",
                question=f"Select root cause for: {state_machine.complaint}",
                causes=zero_causes,
                total_causes=len(zero_causes)
            )
            
            result = self.zero_evidence_agent.analyze(zero_input)
            selected = result.get("selected_root_cause")
            
            if selected:
                # Find original cause to preserve all fields
                original = next(
                    (c for c in causes if c.get("cause_id") == selected.get("cause_id")),
                    selected
                )
                
                original["reason"] = selected.get("reason", "Selected by Zero Evidence agent")
                original["confidence_score"] = selected.get("confidence_score", 0.7)
                original["zero_evidence_reason"] = selected.get("reason", "")
                
                state_machine.control_memory.execution_trace.append(f"4. ZeroEvidenceAgent - Success (selected {original.get('cause_id')})")
                log_agent_call("ZeroEvidenceAgent", {"selected": original.get("cause_id")}, True)
                
                return original
            
            log_error("_call_zero_evidence_for_selection", "No cause selected")
            return causes[0] if causes else None
            
        except Exception as e:
            log_error("_call_zero_evidence_for_selection", str(e))
            log_agent_call("ZeroEvidenceAgent", {}, False, str(e))
            return causes[0] if causes else None
    
    def _validate_input(self, input_data: FishboneInput) -> Optional[str]:
        """Validate input to prevent hallucination"""
        complaint = input_data.complaint.strip() if input_data.complaint else ""
        
        if not complaint:
            return "Invalid input: Complaint description is required and cannot be empty."
        
        if len(complaint) < 10:
            return f"Invalid input: Complaint description is too short ('{complaint}'). Please provide at least 10 characters."
        
        complaint_id = input_data.complaint_id.strip() if input_data.complaint_id else ""
        if not complaint_id:
            return "Invalid input: Complaint ID is required and cannot be empty."
        
        return None
    
    def _create_validation_error_response(self, input_data: FishboneInput, error_msg: str) -> Dict[str, Any]:
        """Create validation error response"""
        return {
            "complaint_id": input_data.complaint_id,
            "root_cause": None,
            "confidence": "LOW",
            "mode": "VALIDATION_ERROR",
            "causes_found": 0,
            "causes": [],
            "category_summary": None,
            "validated_causes_count": 0,
            "high_confidence_causes_count": 0,
            "fmea_document_used": input_data.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "invalid_input",
            "error": error_msg
        }
    
    def _create_error_response(self, input_data: FishboneInput, error_msg: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "complaint_id": input_data.complaint_id,
            "root_cause": None,
            "confidence": "LOW",
            "mode": "ERROR",
            "causes_found": 0,
            "causes": [],
            "category_summary": None,
            "validated_causes_count": 0,
            "high_confidence_causes_count": 0,
            "fmea_document_used": input_data.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "error_occurred",
            "error": f"Orchestrator error: {error_msg}"
        }
    
    def _build_result_from_session(self, session: SessionState) -> Dict[str, Any]:
        """Build result from cached session"""
        # This is a simplified version - in production you'd reconstruct full result
        return {
            "complaint_id": session.complaint_id,
            "root_cause": {
                "cause_id": session.final_root_cause_id,
                "cause_text": "Cached result",
                "process_step": "",
                "source": "CACHED",
                "reason": "Cached from previous analysis"
            } if session.final_root_cause_id else None,
            "confidence": "MEDIUM",
            "mode": "SINGLE_SHOT",
            "causes_found": 0,
            "causes": [],
            "category_summary": None,
            "validated_causes_count": 0,
            "high_confidence_causes_count": 0,
            "fmea_document_used": session.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "cached_result",
            "error": None
        }
