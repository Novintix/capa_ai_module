"""
Fishbone Orchestrator - RCA v2 with Categorization
Integrates: Question Agent (A8), Cause Generation (A9), Categorization Agent (NEW),
            Validation (A10), Ranking Agent (A13), Zero Evidence (A12)

Production Features:
- Session-based memory management per complaint_id
- Redis persistence for session continuity
- Prevents re-evaluation of already-evaluated causes
- Evidence file handling (PDF, DOCX, XLSX, images, logs)
- Validation agent integration with confidence scoring
- **Fishbone categorization at depth 1 (6M categories)**
- Proper state machine with guardrails
- Edge case handling
- Complete audit trail
"""

import time
import os
from typing import Dict, Any, List, Optional
from .schemas import WhyAnalysisInput, WhyAnalysisOutput
from .logger import (
    log_error, log_iteration, log_state_transition,
    log_memory_update, log_llm_context, log_agent_call, log_routing_decision
)
from .state_machine import RCAStateMachine, RCAState, IterationMemory, StopReason
from .session_memory import SessionMemoryManager, SessionState

# Import agents
from Agents.question.agent import WhyQuestionAgent
from Agents.question.schemas import StartWhyInput, ContinueWhyInput
from Agents.cause_generation.schemas import QuestionInput
from Agents.cause_generation.agent import CauseGenerationAgent
from Agents.categorize.state import CategorizeInput, Cause as CategorizeCause, CategorizeState
from Agents.categorize.graph import categorize_graph
from Agents.validation.agent import ValidationAgent
from Agents.validation.schemas import ValidationInput, GeneratedCause
from Agents.ranking.agent import RankingAgent
from Agents.ranking.state import CauseInput as RankingCauseInput
from Agents.zero_evidence_agent.schemas import ZeroEvidenceInput, CauseInput as ZeroEvidenceCauseInput
from Agents.zero_evidence_agent.agent import ZeroEvidenceAgent


class FishboneOrchestratorIntegrated:
    """
    Fishbone Orchestrator with 6M Categorization at Depth 1
    
    Flow: O4 (Orchestrator) → A8 (Question Agent) → A9 (Cause Generation) → 
    **[DEPTH 1 ONLY] → Categorization Agent (6M Categories)** →
    A10 (Validation) → Decision:
        - 0 validated causes: A12 (Zero Evidence - Generate & Stop)
        - 1 validated cause: A11 (Loop Control - Continue)
        - >1 high confidence (≥0.8): A13 (Ranking Agent - Continue)
        - >1 low confidence (<0.8): A12 (Zero Evidence - Select & Stop)
    
    Key Features:
    - Session-based memory per complaint_id (Redis)
    - Prevents re-evaluation of already-evaluated causes
    - Redis-backed Question Agent for SOP compliance
    - **Fishbone categorization at depth 1 (Man, Machine, Method, Material, Measurement, Environment)**
    - Validation Agent with evidence file support (PDF, DOCX, XLSX, images, logs)
    - Confidence-based routing with guardrails
    - Ranking Agent for multiple high-confidence causes
    - Zero Evidence fallback for no FMEA matches
    - Proper state machine with controlled memory
    - Edge case handling and error recovery
    - Complete session continuity and audit trail
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.8  # Validation confidence >= 0.8 = high confidence
    MIN_CONFIDENCE_FOR_CONTINUATION = 0.5  # Minimum confidence to continue iteration
    
    def __init__(self, redis_url: str = None):
        """Initialize all agents and session memory"""
        self.question_agent = WhyQuestionAgent()  # A8
        self.cause_agent = CauseGenerationAgent()  # A9
        self.validation_agent = ValidationAgent()  # A10
        self.ranking_agent = RankingAgent()  # A13
        self.zero_evidence_agent = ZeroEvidenceAgent()  # A12
        
        # Session memory manager
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.session_manager = SessionMemoryManager(redis_url=redis_url)
    
    def analyze(self, input_data: WhyAnalysisInput) -> Dict[str, Any]:
        """
        Run complete RCA v2 Analysis with full agent integration and session management
        
        Args:
            input_data: Input with complaint and optional FMEA
            
        Returns:
            Complete analysis result
        """
        try:
            # Input validation
            validation_error = self._validate_input(input_data)
            if validation_error:
                return self._create_validation_error_response(input_data, validation_error)
            
            # Get or create session
            session = self.session_manager.get_session(input_data.complaint_id)
            
            if session:
                # Existing session found
                if session.is_complete:
                    # Session already complete - return cached result
                    log_memory_update(
                        "orchestrator",
                        input_data.complaint_id,
                        "session_complete",
                        f"Session already complete at depth {session.current_depth}, returning cached result"
                    )
                    return self._build_result_from_session(session)
                
                # Session exists but not complete - this shouldn't happen in normal flow
                # Delete incomplete session and start fresh
                log_memory_update(
                    "orchestrator",
                    input_data.complaint_id,
                    "session_incomplete",
                    f"Found incomplete session at depth {session.current_depth}, starting fresh"
                )
                self.session_manager.delete_session(input_data.complaint_id)
                session = None
            
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
            state_machine = RCAStateMachine(
                complaint_id=input_data.complaint_id,
                complaint=input_data.complaint,
                evidence=input_data.evidence or "",
                sop=input_data.sop or "",
                fmea_document_path=input_data.fmea_document_path,
                max_depth=input_data.max_depth or 5,
                evidence_files=input_data.evidence_files or [],
                logs=input_data.logs,
                reports=input_data.reports,
                process_data=input_data.process_data,
                historical_capa=input_data.historical_capa,
                policies=input_data.policies,
                investigation_records=input_data.investigation_records,
                supporting_system_information=input_data.supporting_system_information
            )
            
            # State machine execution loop
            while state_machine.should_continue():
                success = self._execute_iteration(state_machine, session)
                if not success:
                    state_machine.transition_to(RCAState.ERROR, "Iteration execution failed")
                    break
            
            # Mark session complete
            if state_machine.control_memory.final_root_cause:
                root_cause_id = state_machine.control_memory.final_root_cause.get("cause_id", "UNKNOWN")
                self.session_manager.mark_complete(session, root_cause_id)
            
            # Return final result
            return state_machine.get_final_result()
            
        except Exception as e:
            log_error("analyze", str(e))
            return self._create_error_response(input_data, str(e))
    
    def _execute_iteration(self, state_machine: RCAStateMachine, session: SessionState) -> bool:
        """
        Execute single iteration following the flow diagram with session memory
        
        Flow: A8 → A9 → A10 → Decision → A11/A12/A13
        """
        try:
            # Start new iteration
            state_machine.start_new_iteration()
            
            # ═══════════════════════════════════════════════════════════
            # A8: Question Agent (with SOP, LOGS, TIMELINE)
            # ═══════════════════════════════════════════════════════════
            question = self._call_question_agent(state_machine)
            if not question:
                log_error("_execute_iteration", "Question Agent failed")
                return False
            
            state_machine.transition_to(RCAState.CAUSE_FINDING, "Question generated")
            
            # ═══════════════════════════════════════════════════════════
            # A9: Cause Generation (QMS, PLM)
            # ═══════════════════════════════════════════════════════════
            causes_result = self._call_cause_generation(state_machine, question)
            
            # Guardrail: Check if FMEA exhausted (depth 2+)
            if causes_result.get("method") == "FMEA_EXHAUSTED":
                log_memory_update(
                    "orchestrator",
                    session.complaint_id,
                    "fmea_exhausted",
                    "FMEA exhausted - using last selected cause as root cause"
                )
                state_machine.control_memory.stop_reason = StopReason.FMEA_EXHAUSTED
                
                # Use last selected cause as final root cause
                if state_machine.execution_memory.iterations:
                    last_iteration = state_machine.execution_memory.iterations[-1]
                    if last_iteration.selected_cause:
                        state_machine.control_memory.final_root_cause = last_iteration.selected_cause
                
                return True  # Stop iteration
            
            # Guardrail: If no causes generated at depth 1 (shouldn't happen with LLM fallback)
            if not causes_result.get("causes"):
                if state_machine.control_memory.current_depth == 1:
                    log_error("_execute_iteration", "No causes generated at depth 1 even with LLM fallback")
                    state_machine.control_memory.stop_reason = StopReason.NO_CAUSES_FOUND
                else:
                    log_error("_execute_iteration", "No causes generated at depth 2+")
                    state_machine.control_memory.stop_reason = StopReason.FMEA_EXHAUSTED
                return True
            
            # ═══════════════════════════════════════════════════════════
            # SESSION MEMORY: Filter already-evaluated causes
            # ═══════════════════════════════════════════════════════════
            causes_before_filter = len(causes_result["causes"])
            causes_result["causes"] = self.session_manager.filter_unevaluated_causes(
                session,
                causes_result["causes"]
            )
            causes_after_filter = len(causes_result["causes"])
            
            if causes_after_filter < causes_before_filter:
                log_memory_update(
                    "orchestrator",
                    session.complaint_id,
                    "filter_duplicates",
                    f"Filtered {causes_before_filter - causes_after_filter} already-evaluated causes"
                )
            
            # Guardrail: If all causes were already evaluated, stop
            if not causes_result["causes"]:
                log_memory_update(
                    "orchestrator",
                    session.complaint_id,
                    "all_evaluated",
                    "All causes already evaluated in previous iterations"
                )
                state_machine.control_memory.stop_reason = StopReason.CAUSE_REPETITION
                return True
            
            # ═══════════════════════════════════════════════════════════
            # CATEGORIZATION: Only at Depth 1 (Fishbone 6M Categories)
            # ═══════════════════════════════════════════════════════════
            if state_machine.control_memory.current_depth == 1:
                categorization_result = self._call_categorization_agent(
                    state_machine,
                    question,
                    causes_result["causes"]
                )
                causes_result["causes"] = categorization_result["categorized_causes"]
                log_memory_update(
                    "orchestrator",
                    session.complaint_id,
                    "categorization",
                    f"Categorized {len(causes_result['causes'])} causes into 6M categories"
                )
            
            state_machine.transition_to(RCAState.VALIDATION, "Causes generated and categorized")
            
            # ═══════════════════════════════════════════════════════════
            # A10: Validation (PLM, QMS, ERP, LOGS, TIMELINE, Evidence Files)
            # ═══════════════════════════════════════════════════════════
            validation_result = self._call_validation_agent(state_machine, question, causes_result["causes"])
            
            # ═══════════════════════════════════════════════════════════
            # Decision Logic based on validation
            # ═══════════════════════════════════════════════════════════
            num_validated = validation_result["num_validated"]
            high_confidence_count = validation_result["high_confidence_count"]
            
            selected_cause = None
            
            if num_validated == 0:
                # ═══ Path: 0 validated causes → A12 (Zero Evidence - Select from unvalidated & Stop) ═══
                log_routing_decision("validation", "zero_evidence", "No validated causes - select from unvalidated causes")
                state_machine.transition_to(RCAState.ZERO_EVIDENCE, "No validated causes")
                
                # Use Zero Evidence to select from the original causes (even though unvalidated)
                # This is better than generating new causes - we use what FMEA/LLM provided
                if causes_result.get("causes"):
                    selected_cause = self._call_zero_evidence_for_selection(
                        state_machine,
                        question,
                        causes_result["causes"]  # Use original causes, not validated ones
                    )
                    
                    # Add justification
                    if selected_cause and not selected_cause.get("selection_justification"):
                        zero_reason = selected_cause.get("zero_evidence_reason", "Selected by Zero Evidence agent")
                        selected_cause["selection_justification"] = (
                            f"No validated causes found. {zero_reason}"
                        )
                else:
                    # Only generate new causes if we have absolutely nothing
                    selected_cause = self._handle_zero_causes(state_machine, question)
                    
                    # Add justification
                    if selected_cause and not selected_cause.get("selection_justification"):
                        selected_cause["selection_justification"] = (
                            "No causes found in FMEA. Generated with LLM and selected by Zero Evidence agent."
                        )
                
                state_machine.control_memory.stop_reason = StopReason.NO_CAUSES_FOUND
                
            elif high_confidence_count > 1:
                # ═══ Path: >1 high confidence → A13 (Ranking Agent - Continue) ═══
                log_routing_decision("validation", "ranking_agent", f"{high_confidence_count} high confidence causes")
                state_machine.transition_to(RCAState.CAUSE_RANKING, "Multiple high confidence causes")
                selected_cause = self._call_ranking_agent(
                    state_machine,
                    question,
                    validation_result["high_confidence_causes"]
                )
                
            elif high_confidence_count == 1:
                # ═══ Path: 1 high confidence → Select it and Continue ═══
                log_routing_decision("validation", "loop_control", "Single high confidence cause - continue iteration")
                selected_cause = {**validation_result["high_confidence_causes"][0]}
                
                # Add comprehensive justification with evidence details
                validation_conf = selected_cause.get('validation_confidence', 0.0)
                validation_rationale = selected_cause.get('validation_rationale', '')
                supporting_evidence = selected_cause.get('supporting_evidence', [])
                
                justification_parts = [
                    f"High confidence validated cause (confidence: {validation_conf:.2f})."
                ]
                
                if validation_rationale:
                    # Include first 150 chars of rationale
                    rationale_preview = validation_rationale[:150] + "..." if len(validation_rationale) > 150 else validation_rationale
                    justification_parts.append(f"Rationale: {rationale_preview}")
                
                if supporting_evidence:
                    evidence_refs = ', '.join(supporting_evidence[:5])
                    justification_parts.append(f"Evidence refs: {evidence_refs}")
                
                selected_cause["selection_justification"] = " ".join(justification_parts)
                
            else:
                # ═══ Path: Only low confidence causes → A12 (Zero Evidence - Select & Stop) ═══
                log_routing_decision("validation", "zero_evidence", "Only low confidence causes - use Zero Evidence")
                state_machine.transition_to(RCAState.ZERO_EVIDENCE, "Low confidence causes")
                
                # Use Zero Evidence to select from low confidence causes
                selected_cause = self._call_zero_evidence_for_selection(
                    state_machine,
                    question,
                    validation_result["validated_causes"]
                )
                
                # Add justification from Zero Evidence
                if selected_cause and not selected_cause.get("selection_justification"):
                    zero_reason = selected_cause.get("zero_evidence_reason", "Selected by Zero Evidence agent")
                    selected_cause["selection_justification"] = (
                        f"Multiple low confidence causes found. {zero_reason}"
                    )
                
                # Stop after Zero Evidence selection
                state_machine.control_memory.stop_reason = StopReason.SINGLE_SHOT_COMPLETE
            
            # Guardrail: If no cause selected, use fallback
            if not selected_cause:
                log_error("_execute_iteration", "No cause selected - using fallback")
                if validation_result["validated_causes"]:
                    selected_cause = validation_result["validated_causes"][0]
                elif causes_result.get("causes"):
                    selected_cause = causes_result["causes"][0]
                else:
                    return False
            
            # ═══════════════════════════════════════════════════════════
            # SESSION MEMORY: Add iteration to session
            # ═══════════════════════════════════════════════════════════
            self.session_manager.add_iteration(
                session=session,
                question=question,
                causes_evaluated=validation_result["all_causes"],
                selected_cause=selected_cause,
                validation_confidence=validation_result.get("overall_confidence", 0.0)
            )
            
            # Create iteration memory
            iteration = IterationMemory(
                depth=state_machine.control_memory.current_depth,
                question=question,
                causes_found=validation_result["all_causes"],  # All causes (validated + unvalidated)
                validated_causes=validation_result["validated_causes"],
                selected_cause=selected_cause,
                fmea_matches=causes_result.get("fmea_matches", 0),
                generation_method=causes_result.get("method", "unknown"),
                validation_confidence=validation_result.get("overall_confidence", 0.0),
                selection_justification=selected_cause.get("selection_justification") if selected_cause else None
            )
            
            # Complete iteration (updates memories and determines next state)
            state_machine.complete_iteration(iteration)
            
            # Log iteration
            log_iteration(
                iteration.depth,
                iteration.question,
                len(iteration.causes_found),
                selected_cause.get("cause_text") if selected_cause else None
            )
            
            return True
            
        except Exception as e:
            log_error("_execute_iteration", f"Iteration failed: {str(e)}")
            return False

    
    def _call_question_agent(self, state_machine: RCAStateMachine) -> Optional[str]:
        """
        A8: Question Agent - Generate Why question with Redis context
        
        Features: SOP compliance, LOGS, TIMELINE tracking
        """
        try:
            complaint_id = state_machine.complaint_id
            current_depth = state_machine.control_memory.current_depth
            
            if current_depth == 1:
                # Start new chain
                input_data = StartWhyInput(
                    complaint_id=complaint_id,
                    complaint=state_machine.complaint,
                    evidence=state_machine.evidence,
                    sop=state_machine.sop
                )
                
                result = self.question_agent.start(input_data)
                
            else:
                # Continue chain
                last_iteration = state_machine.execution_memory.iterations[-1]
                answer = last_iteration.selected_cause.get("cause_text", "") if last_iteration.selected_cause else ""
                
                input_data = ContinueWhyInput(
                    complaint_id=complaint_id,
                    answer=answer
                )
                
                result = self.question_agent.continue_chain(input_data)
            
            # Check for errors from Question Agent
            if result.get("error"):
                log_error("_call_question_agent", f"Question Agent returned error: {result.get('error')}")
                log_agent_call("QuestionAgent", {"complaint_id": complaint_id}, False, result.get("error"))
                return None
            
            question = result.get("why_question")
            
            # Guardrail: Validate question quality
            if not question:
                log_error("_call_question_agent", f"Question Agent returned None for why_question. Full result: {result}")
                log_agent_call("QuestionAgent", {"complaint_id": complaint_id}, False, "why_question is None")
                return None
            
            question = question.strip()
            if len(question) < 3:
                log_error("_call_question_agent", f"Question too short: '{question}' (length: {len(question)})")
                log_agent_call("QuestionAgent", {"complaint_id": complaint_id}, False, f"Question too short: {question}")
                return None
            
            # Success
            log_agent_call("QuestionAgent", {"complaint_id": complaint_id, "question_length": len(question)}, True)
            log_llm_context(complaint_id, "question_generation", len(question))
            
            return question
            
        except Exception as e:
            log_error("_call_question_agent", str(e))
            log_agent_call("QuestionAgent", {"complaint_id": state_machine.complaint_id}, False, str(e))
            return None
    
    def _call_cause_generation(self, state_machine: RCAStateMachine, question: str) -> Dict[str, Any]:
        """
        A9: Cause Generation - Generate causes from FMEA, Evidence, and Reports
        
        Features: QMS, PLM integration + Evidence-based cause extraction
        
        Enhanced Logic:
        - Extract causes from FMEA (semantic matching)
        - Extract causes from evidence/reports (direct mentions)
        - Combine and deduplicate
        
        Fallback Logic:
        - Depth 1: If no causes found → Generate with LLM
        - Depth 2+: If FMEA returns no causes → FMEA exhausted, return empty
        """
        try:
            # Prepare evidence context for cause extraction
            evidence_context = {
                "evidence": state_machine.evidence,
                "logs": state_machine.logs or [],
                "reports": state_machine.reports or [],
                "investigation_records": state_machine.investigation_records or [],
                "historical_capa": state_machine.historical_capa or ""
            }
            
            question_input = QuestionInput(
                question_id=f"{state_machine.complaint_id}_depth{state_machine.control_memory.current_depth}",
                question=question,
                context=state_machine.complaint,
                evidence_context=evidence_context  # Pass evidence for extraction
            )
            
            current_depth = state_machine.control_memory.current_depth
            
            # Call cause generation agent with FMEA and evidence
            result = self.cause_agent.process_question(
                question_input,
                state_machine.fmea_document_path
            )
            
            causes = result.get("causes", [])
            fmea_matches = result.get("matched_entries", 0)
            evidence_extracted = result.get("evidence_extracted", 0)
            
            # CRITICAL FALLBACK LOGIC
            if not causes and state_machine.fmea_document_path:
                if current_depth == 1:
                    # Depth 1: No FMEA causes → Generate with LLM → Zero Evidence will handle
                    log_memory_update(
                        "cause_generation",
                        "fallback_depth1",
                        "llm",
                        "FMEA returned no causes at depth 1, generating with LLM for Zero Evidence mode"
                    )
                    result = self.cause_agent.process_question(question_input, None)  # Force LLM
                    causes = result.get("causes", [])
                    fmea_matches = 0
                    evidence_extracted = 0
                else:
                    # Depth 2+: No FMEA causes → FMEA exhausted → Use last selected cause as root
                    log_memory_update(
                        "cause_generation",
                        "fmea_exhausted",
                        "stop",
                        f"FMEA exhausted at depth {current_depth}, no more causes available"
                    )
                    # Return empty - orchestrator will handle stopping with last cause
                    return {
                        "causes": [],
                        "fmea_matches": 0,
                        "method": "FMEA_EXHAUSTED"
                    }
            
            # Filter duplicates from previous iterations
            if state_machine.execution_memory.iterations:
                causes = self._filter_duplicate_causes(causes, state_machine.execution_memory.iterations)
            
            # Determine method
            if evidence_extracted > 0 and fmea_matches > 0:
                method = "FMEA+Evidence"
            elif evidence_extracted > 0:
                method = "Evidence"
            elif fmea_matches > 0:
                method = "FMEA"
            else:
                method = "LLM_Generated"
            
            log_agent_call(
                "CauseGenerationAgent",
                {
                    "question_id": question_input.question_id,
                    "causes_found": len(causes),
                    "fmea_matches": fmea_matches,
                    "evidence_extracted": evidence_extracted,
                    "method": method
                },
                True
            )
            
            return {
                "causes": causes,
                "fmea_matches": fmea_matches,
                "evidence_extracted": evidence_extracted,
                "method": method
            }
            
        except Exception as e:
            log_error("_call_cause_generation", str(e))
            log_agent_call("CauseGenerationAgent", {}, False, str(e))
            return {"causes": [], "fmea_matches": 0, "method": "error"}
    
    def _call_categorization_agent(self, state_machine: RCAStateMachine, question: str, causes: List[Dict]) -> Dict[str, Any]:
        """
        Categorization Agent - Categorize causes into 6M categories (Fishbone)
        
        Only called at DEPTH 1 for fishbone diagram categorization.
        
        Categories: Man, Machine, Method, Material, Measurement, Environment
        
        Args:
            state_machine: Current state machine
            question: Why question
            causes: List of causes to categorize
            
        Returns:
            {
                "categorized_causes": List[Dict],  # Causes with category field added
                "category_summary": Dict[str, int]  # Count per category
            }
        """
        try:
            log_agent_call("CategorizationAgent", {"causes_count": len(causes)}, None, None)
            
            # Convert causes to categorize format
            categorize_causes = []
            for cause in causes:
                categorize_causes.append(CategorizeCause(
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
                question=question,
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
                    # Find matching categorized cause
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
                    {
                        "categorized_count": len(categorized_causes),
                        "category_summary": category_summary
                    },
                    True
                )
                
                return {
                    "categorized_causes": categorized_causes,
                    "category_summary": category_summary
                }
            else:
                # Categorization failed, return causes without categories
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
                cause["category_reasoning"] = f"Categorization error: {str(e)}"
                cause["secondary_categories"] = []
            
            return {
                "categorized_causes": causes,
                "category_summary": {"Unknown": len(causes)}
            }
    
    def _call_validation_agent(self, state_machine: RCAStateMachine, question: str, causes: List[Dict]) -> Dict[str, Any]:
        """
        A10: Validation Agent - Validate causes against evidence
        
        Features: PLM, QMS, ERP, LOGS, TIMELINE, Evidence Files (PDF, DOCX, XLSX, images, logs)
        
        Returns:
            {
                "num_validated": int,
                "high_confidence_count": int,
                "validated_causes": List[Dict],  # Only matched/partially_matched
                "high_confidence_causes": List[Dict],  # confidence >= 0.8
                "all_causes": List[Dict],  # All causes with validation status
                "overall_confidence": float
            }
        """
        try:
            # Prepare causes for validation
            generated_causes = []
            for cause in causes:
                generated_causes.append(GeneratedCause(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step"),
                    failure_mode=cause.get("failure_mode"),
                    potential_effects=cause.get("potential_effects"),
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "cause_generation")
                ))
            
            # Create validation input
            validation_input = ValidationInput(
                complaint_id=state_machine.complaint_id,
                question=question,
                generated_causes=generated_causes,
                complaint_description=state_machine.complaint,
                logs=state_machine.logs,
                reports=state_machine.reports,
                process_data=state_machine.process_data,
                historical_capa=state_machine.historical_capa,
                policies=state_machine.policies,
                sop=state_machine.sop,
                investigation_records=state_machine.investigation_records,
                supporting_system_information=state_machine.supporting_system_information,
                evidence_files=state_machine.evidence_files
            )
            
            # Call validation agent
            validation_result = self.validation_agent.validate_causes(validation_input)
            
            # Extract validated causes (matched or partially_matched)
            validated_causes_from_agent = validation_result.get("validated_causes", [])
            all_validation_results = validation_result.get("cause_validation_results", [])
            
            # CRITICAL: Merge validation results back with original FMEA causes
            # The validation agent returns only validation metadata, we need to preserve FMEA fields
            validated_causes_with_fmea = []
            for val_cause in validated_causes_from_agent:
                val_cause_id = val_cause.get("cause_id")
                
                # Find original cause with all FMEA fields
                for original_cause in causes:
                    if original_cause.get("cause_id") == val_cause_id:
                        # Merge: Start with original cause (has all FMEA fields)
                        merged_cause = {**original_cause}
                        
                        # Add validation metadata
                        merged_cause["validation_status"] = val_cause.get("evidence_match_status", "matched")
                        merged_cause["validation_confidence"] = val_cause.get("confidence", 0.0)
                        merged_cause["validation_rationale"] = val_cause.get("rationale", "")
                        merged_cause["supporting_evidence"] = val_cause.get("supporting_evidence_references", [])
                        
                        validated_causes_with_fmea.append(merged_cause)
                        break
            
            # Separate high confidence causes (confidence >= 0.8)
            high_confidence_causes = []
            for cause in validated_causes_with_fmea:
                if cause.get("validation_confidence", 0.0) >= self.HIGH_CONFIDENCE_THRESHOLD:
                    high_confidence_causes.append(cause)
            
            # Merge validation results back into ALL original causes (for tracking)
            all_causes_with_validation = []
            for cause in causes:
                cause_id = cause.get("cause_id")
                
                # Find validation result
                validation_status = None
                for val_result in all_validation_results:
                    if val_result.get("cause_id") == cause_id:
                        validation_status = val_result
                        break
                
                # Merge
                cause_with_validation = {**cause}
                if validation_status:
                    cause_with_validation["validation_status"] = validation_status.get("evidence_match_status", "no_evidence")
                    cause_with_validation["validation_confidence"] = validation_status.get("confidence", 0.0)
                    cause_with_validation["validation_rationale"] = validation_status.get("rationale", "")
                    cause_with_validation["supporting_evidence"] = validation_status.get("supporting_evidence_references", [])
                else:
                    cause_with_validation["validation_status"] = "not_validated"
                    cause_with_validation["validation_confidence"] = 0.0
                
                all_causes_with_validation.append(cause_with_validation)
            
            log_agent_call(
                "ValidationAgent",
                {
                    "total_causes": len(causes),
                    "validated": len(validated_causes_with_fmea),
                    "high_confidence": len(high_confidence_causes)
                },
                True
            )
            
            log_memory_update(
                "validation",
                "cause_validation",
                "validate",
                f"Total: {len(causes)}, Validated: {len(validated_causes_with_fmea)}, High confidence: {len(high_confidence_causes)}"
            )
            
            return {
                "num_validated": len(validated_causes_with_fmea),
                "high_confidence_count": len(high_confidence_causes),
                "validated_causes": validated_causes_with_fmea,  # With FMEA fields preserved
                "high_confidence_causes": high_confidence_causes,  # With FMEA fields preserved
                "all_causes": all_causes_with_validation,
                "overall_confidence": validation_result.get("overall_confidence", 0.0)
            }
            
        except Exception as e:
            log_error("_call_validation_agent", str(e))
            log_agent_call("ValidationAgent", {}, False, str(e))
            
            # Fallback: Return all causes as unvalidated
            return {
                "num_validated": 0,
                "high_confidence_count": 0,
                "validated_causes": [],
                "high_confidence_causes": [],
                "all_causes": causes,
                "overall_confidence": 0.0
            }
    
    def _call_ranking_agent(self, state_machine: RCAStateMachine, question: str, causes: List[Dict]) -> Optional[Dict]:
        """
        A13: Ranking Agent - Rank multiple high-confidence causes
        
        Features: QMS integration, RCPS methodology
        """
        try:
            # Prepare causes for ranking
            ranking_causes = []
            for cause in causes[:10]:  # Limit to top 10
                # Extract validation confidence
                validation_confidence = cause.get("confidence", cause.get("validation_confidence", 0.8))
                
                ranking_causes.append({
                    "cause_id": cause.get("cause_id", "UNKNOWN"),
                    "cause_text": cause.get("cause_text", ""),
                    "process_step": cause.get("process_step") or "Unknown",  # Fix: Provide default
                    "failure_mode": cause.get("failure_mode") or "Unknown",  # Fix: Provide default
                    "potential_effects": cause.get("potential_effects") or "Unknown",  # Fix: Provide default
                    "severity": cause.get("severity", 5),
                    "occurrence": cause.get("occurrence", 5),
                    "detection": cause.get("detection", 5),
                    "evidence_strength": validation_confidence,  # Use validation confidence
                    "mechanism_fit": 0.8,  # Default
                    "causal_proximity": 0.9  # Default
                })
            
            # Call ranking agent
            result = self.ranking_agent.rank_causes(ranking_causes)
            
            # Get selected root cause ID
            selected_id = result.selected_root_cause
            
            # Find original cause with all fields
            selected_cause = None
            for cause in causes:
                if cause.get("cause_id") == selected_id:
                    selected_cause = {**cause}  # Copy all fields
                    
                    # Add ranking justification
                    for ranked in result.ranked_causes:
                        if ranked.cause_id == selected_id:
                            selected_cause["selection_justification"] = (
                                f"Selected by Ranking Agent (RCPS: {ranked.rcps_score:.2f}). "
                                f"Ranked #1 out of {len(causes)} high-confidence causes. "
                                f"RPN: {ranked.rpn}, Evidence: {ranked.evidence_strength:.2f}, "
                                f"Risk Level: {ranked.risk_level}"
                            )
                            break
                    break
            
            # Guardrail: If not found, use first ranked cause
            if not selected_cause and result.ranked_causes:
                first_ranked = result.ranked_causes[0]
                for cause in causes:
                    if cause.get("cause_id") == first_ranked.cause_id:
                        selected_cause = {**cause}
                        selected_cause["selection_justification"] = (
                            f"Selected by Ranking Agent (RCPS: {first_ranked.rcps_score:.2f})"
                        )
                        break
            
            log_agent_call("RankingAgent", {"num_causes": len(ranking_causes), "selected": selected_id}, True)
            
            return selected_cause
            
        except Exception as e:
            log_error("_call_ranking_agent", str(e))
            log_agent_call("RankingAgent", {}, False, str(e))
            # Fallback to first cause with justification
            if causes:
                fallback_cause = {**causes[0]}
                fallback_cause["selection_justification"] = "Selected as fallback (Ranking Agent failed)"
                return fallback_cause
            return None

    
    def _handle_zero_causes(self, state_machine: RCAStateMachine, question: str) -> Optional[Dict]:
        """
        A12: Zero Evidence Mode - Handle no validated causes (generate mode)
        
        Generates causes using LLM when validation finds no evidence
        """
        try:
            # Generate causes using LLM (no FMEA)
            question_input = QuestionInput(
                question_id=f"{state_machine.complaint_id}_zero_evidence",
                question=question,
                context=state_machine.complaint
            )
            
            result = self.cause_agent.process_question(question_input, None)  # Force LLM
            causes = result.get("causes", [])
            
            if not causes:
                log_error("_handle_zero_causes", "Zero Evidence mode failed to generate causes")
                return None
            
            # Use Zero Evidence agent to select best cause
            cause_inputs = []
            for cause in causes[:5]:  # Limit to 5
                cause_inputs.append(ZeroEvidenceCauseInput(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", "Unknown"),
                    failure_mode=cause.get("failure_mode", "Unknown"),
                    potential_effects=cause.get("potential_effects"),
                    severity=cause.get("severity"),
                    occurrence=cause.get("occurrence"),
                    detection=cause.get("detection"),
                    current_controls=cause.get("current_controls"),
                    source="LLM_Generated"
                ))
            
            zero_input = ZeroEvidenceInput(
                question_id=question_input.question_id,
                question=question,
                causes=cause_inputs,
                total_causes=len(cause_inputs)
            )
            
            zero_result = self.zero_evidence_agent.analyze(zero_input)
            selected = zero_result.get("selected_root_cause")
            
            if not selected:
                log_error("_handle_zero_causes", "Zero Evidence agent failed to select cause")
                return causes[0] if causes else None
            
            # Convert to standard format
            selected_cause = {
                "cause_id": selected.get("cause_id"),
                "cause_text": selected.get("cause_text"),
                "process_step": selected.get("process_step"),
                "failure_mode": "Unknown",
                "source": "LLM_Generated",
                "validation_status": "zero_evidence",
                "validation_confidence": 0.5,
                "validation_rationale": selected.get("reason", "Selected by Zero Evidence agent")
            }
            
            log_agent_call("ZeroEvidenceAgent", {"mode": "generate", "reason": "no_validated_causes"}, True)
            
            return selected_cause
            
        except Exception as e:
            log_error("_handle_zero_causes", str(e))
            log_agent_call("ZeroEvidenceAgent", {}, False, str(e))
            return None
    
    def _call_zero_evidence_for_selection(self, state_machine: RCAStateMachine, question: str, causes: List[Dict]) -> Optional[Dict]:
        """
        A12: Zero Evidence Mode - Select from causes (validated or unvalidated)
        
        Uses Zero Evidence agent to select best cause based on criticality scoring
        Preserves all original cause fields (FMEA data, validation status, etc.)
        """
        try:
            if not causes:
                log_error("_call_zero_evidence_for_selection", "No causes provided")
                return None
            
            # Prepare causes for Zero Evidence agent
            cause_inputs = []
            for cause in causes[:10]:  # Limit to 10 for performance
                cause_inputs.append(ZeroEvidenceCauseInput(
                    cause_id=cause.get("cause_id", "UNKNOWN"),
                    cause_text=cause.get("cause_text", ""),
                    process_step=cause.get("process_step", "Unknown"),
                    failure_mode=cause.get("failure_mode", "Unknown"),
                    potential_effects=cause.get("potential_effects"),
                    severity=cause.get("severity", 5),
                    occurrence=cause.get("occurrence", 5),
                    detection=cause.get("detection", 5),
                    current_controls=cause.get("current_controls"),
                    source=cause.get("source", "FMEA")
                ))
            
            zero_input = ZeroEvidenceInput(
                question_id=f"{state_machine.complaint_id}_depth{state_machine.control_memory.current_depth}",
                question=question,
                causes=cause_inputs,
                total_causes=len(cause_inputs)
            )
            
            zero_result = self.zero_evidence_agent.analyze(zero_input)
            selected = zero_result.get("selected_root_cause")
            
            if not selected:
                log_error("_call_zero_evidence_for_selection", "Zero Evidence agent returned no selection")
                return causes[0] if causes else None
            
            # Find original cause with ALL fields preserved
            selected_cause = None
            selected_id = selected.get("cause_id")
            
            for cause in causes:
                if cause.get("cause_id") == selected_id:
                    # Found it - return original cause with all fields
                    selected_cause = {**cause}  # Copy all fields
                    
                    # Add Zero Evidence metadata
                    selected_cause["zero_evidence_reason"] = selected.get("reason", "Selected by Zero Evidence agent")
                    selected_cause["zero_evidence_mode"] = "selection"
                    
                    log_agent_call(
                        "ZeroEvidenceAgent",
                        {
                            "mode": "select",
                            "num_causes": len(causes),
                            "selected_id": selected_id,
                            "selected_text": selected_cause.get("cause_text", "")[:50]
                        },
                        True
                    )
                    
                    return selected_cause
            
            # Fallback: If cause_id not found, use first cause
            log_error("_call_zero_evidence_for_selection", f"Selected cause_id {selected_id} not found in original causes")
            return causes[0] if causes else None
            
        except Exception as e:
            log_error("_call_zero_evidence_for_selection", str(e))
            log_agent_call("ZeroEvidenceAgent", {}, False, str(e))
            # Fallback to first cause
            return causes[0] if causes else None
    
    def _filter_duplicate_causes(self, causes: List[Dict], previous_iterations: List[IterationMemory]) -> List[Dict]:
        """Filter out previously selected causes"""
        if not previous_iterations:
            return causes
        
        previous_causes = []
        for iteration in previous_iterations:
            if iteration.selected_cause:
                previous_causes.append(iteration.selected_cause.get("cause_text", "").lower().strip())
        
        filtered = []
        for cause in causes:
            cause_text = cause.get("cause_text", "").lower().strip()
            if cause_text not in previous_causes:
                filtered.append(cause)
        
        return filtered
    
    def _build_result_from_session(self, session: SessionState) -> Dict[str, Any]:
        """
        Build analysis result from cached session
        
        NOTE: Cached results contain limited detail (cause IDs and texts only).
        Full FMEA fields, validation evidence, and selection justifications are not stored
        in Redis for efficiency. To get full details, delete the session and re-run analysis.
        
        Args:
            session: Completed session state
            
        Returns:
            Complete analysis result matching WhyAnalysisOutput schema (with limited detail)
        """
        # Build root cause from final selected cause
        root_cause = None
        if session.final_root_cause_id and session.iterations:
            # Find the iteration with the final root cause
            for iteration in reversed(session.iterations):
                if iteration.selected_cause_id == session.final_root_cause_id:
                    root_cause = {
                        "cause_id": iteration.selected_cause_id,
                        "cause_text": iteration.selected_cause_text,
                        "process_step": "N/A (cached)",  # Not stored in session
                        "failure_mode": None,
                        "potential_effects": None,
                        "severity": None,
                        "occurrence": None,
                        "detection": None,
                        "current_controls": None,
                        "source": "CACHED",
                        "reason": "Cached from previous analysis - full details not available",
                        "confidence_score": iteration.validation_confidence
                    }
                    break
        
        # Build iterations
        why_iterations = []
        for iteration in session.iterations:
            why_iterations.append({
                "depth": iteration.depth,
                "question": iteration.question,
                "reasoning": f"Cached result from previous analysis at depth {iteration.depth}",
                "causes_found": len(iteration.causes_evaluated),
                "causes": [],  # Not stored in session for efficiency
                "selected_cause": {
                    "cause_id": iteration.selected_cause_id,
                    "cause_text": iteration.selected_cause_text,
                    "process_step": "N/A (cached)",
                    "failure_mode": None,
                    "potential_effects": None,
                    "severity": None,
                    "occurrence": None,
                    "detection": None,
                    "current_controls": None,
                    "source": "CACHED"
                },
                "selection_justification": "Cached result - full justification not available. Delete session and re-run for full details.",
                "fmea_matches": 0,  # Not stored
                "generation_method": "CACHED"
            })
        
        # Determine confidence
        confidence = "MEDIUM"
        if session.current_depth >= 3:
            confidence = "HIGH"
        elif session.current_depth < 2:
            confidence = "LOW"
        
        # Calculate execution time (instant for cached)
        execution_time = 0.0  # Cached results are instant
        
        return {
            "complaint_id": session.complaint_id,
            "root_cause": root_cause,
            "confidence": confidence,
            "mode": "FMEA_ITERATIVE" if session.fmea_document_path else "NO_FMEA_SINGLE_SHOT",
            "analysis_depth": session.current_depth,
            "why_iterations": why_iterations,
            "total_causes_analyzed": len(session.all_evaluated_cause_ids),
            "fmea_document_used": session.fmea_document_path,
            "execution_time_seconds": execution_time,
            "stopping_reason": "cached_result",
            "error": "NOTE: This is a cached result with limited detail. For full FMEA fields, validation evidence, and selection justifications, delete the session and re-run the analysis."
        }
    
    def _validate_input(self, input_data: WhyAnalysisInput) -> Optional[str]:
        """Validate input with comprehensive guardrails"""
        complaint = input_data.complaint.strip() if input_data.complaint else ""
        
        # Guardrail 1: Required fields
        if not complaint:
            return "Invalid input: Complaint description is required"
        
        if not input_data.complaint_id.strip():
            return "Invalid input: Complaint ID required"
        
        # Guardrail 2: Minimum length
        if len(complaint) < 10:
            return f"Invalid input: Complaint too short (minimum 10 characters, got {len(complaint)})"
        
        # Guardrail 3: Placeholder detection
        generic_phrases = ["test", "testing", "example", "sample", "demo", "placeholder"]
        if any(phrase in complaint.lower() for phrase in generic_phrases) and len(complaint) < 50:
            return f"Invalid input: Placeholder text detected ('{complaint}')"
        
        # Guardrail 4: Max depth validation (removed - system runs until root cause found)
        # No max_depth validation - system will run until natural stopping conditions
        
        return None
    
    def _create_validation_error_response(self, input_data: WhyAnalysisInput, error_msg: str) -> Dict[str, Any]:
        """Create validation error response"""
        return {
            "complaint_id": input_data.complaint_id,
            "root_cause": None,
            "confidence": "LOW",
            "mode": "VALIDATION_ERROR",
            "analysis_depth": 0,
            "why_iterations": [],
            "total_causes_analyzed": 0,
            "fmea_document_used": input_data.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "invalid_input",
            "error": error_msg
        }
    
    def _create_error_response(self, input_data: WhyAnalysisInput, error_msg: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "complaint_id": input_data.complaint_id,
            "root_cause": None,
            "confidence": "LOW",
            "mode": "ERROR",
            "analysis_depth": 0,
            "why_iterations": [],
            "total_causes_analyzed": 0,
            "fmea_document_used": input_data.fmea_document_path,
            "execution_time_seconds": 0.0,
            "stopping_reason": "error_occurred",
            "error": f"Orchestrator error: {error_msg}"
        }



