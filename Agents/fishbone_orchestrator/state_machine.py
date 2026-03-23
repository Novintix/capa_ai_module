"""
RCA v2 State Machine
Proper state management with controlled memory and LLM context
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import time


class RCAState(Enum):
    """Defined states for RCA analysis"""
    INITIALIZING = "initializing"
    QUESTIONING = "questioning"
    CAUSE_FINDING = "cause_finding"
    VALIDATION = "validation"
    CAUSE_RANKING = "cause_ranking"
    ZERO_EVIDENCE = "zero_evidence"
    ITERATION_COMPLETE = "iteration_complete"
    ANALYSIS_COMPLETE = "analysis_complete"
    ERROR = "error"


class StopReason(Enum):
    """Reasons for stopping analysis"""
    COMPLETED = "completed"
    MAX_DEPTH_REACHED = "max_depth_reached"
    NO_CAUSES_FOUND = "no_causes_found"
    CAUSE_REPETITION = "cause_repetition"
    SINGLE_SHOT_COMPLETE = "single_shot_complete"
    FMEA_EXHAUSTED = "fmea_exhausted"
    ERROR_OCCURRED = "error_occurred"
    INVALID_INPUT = "invalid_input"


@dataclass
class IterationMemory:
    """Memory for a single iteration"""
    depth: int
    question: str
    causes_found: List[Dict[str, Any]]
    selected_cause: Optional[Dict[str, Any]]
    fmea_matches: int
    generation_method: str
    validated_causes: List[Dict[str, Any]] = field(default_factory=list)
    validation_confidence: float = 0.0
    selection_justification: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionMemory:
    """Complete execution history - orchestrator only"""
    iterations: List[IterationMemory] = field(default_factory=list)
    total_causes_analyzed: int = 0
    start_time: float = field(default_factory=time.time)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_iteration(self, iteration: IterationMemory):
        """Add iteration to memory"""
        self.iterations.append(iteration)
        self.total_causes_analyzed += len(iteration.causes_found)
    
    def get_execution_time(self) -> float:
        """Get total execution time"""
        return time.time() - self.start_time
    
    def log_state_transition(self, from_state: RCAState, to_state: RCAState, reason: str):
        """Log state transition"""
        self.state_transitions.append({
            "from": from_state.value,
            "to": to_state.value,
            "reason": reason,
            "timestamp": time.time()
        })


@dataclass
class ControlMemory:
    """Control state and decisions - orchestrator only"""
    current_state: RCAState = RCAState.INITIALIZING
    current_depth: int = 0
    max_depth: int = 5
    mode: str = "NO_FMEA_SINGLE_SHOT"
    stop_reason: Optional[StopReason] = None
    confidence_level: str = "MEDIUM"
    final_root_cause: Optional[Dict[str, Any]] = None
    
    def can_transition_to(self, new_state: RCAState) -> bool:
        """Validate state transition"""
        valid_transitions = {
            RCAState.INITIALIZING: [RCAState.QUESTIONING, RCAState.ERROR],
            RCAState.QUESTIONING: [RCAState.CAUSE_FINDING, RCAState.ERROR],
            RCAState.CAUSE_FINDING: [RCAState.VALIDATION, RCAState.ANALYSIS_COMPLETE, RCAState.ERROR],
            RCAState.VALIDATION: [RCAState.CAUSE_RANKING, RCAState.ZERO_EVIDENCE, RCAState.ITERATION_COMPLETE, RCAState.ANALYSIS_COMPLETE, RCAState.ERROR],
            RCAState.CAUSE_RANKING: [RCAState.ITERATION_COMPLETE, RCAState.ANALYSIS_COMPLETE, RCAState.ERROR],
            RCAState.ZERO_EVIDENCE: [RCAState.ANALYSIS_COMPLETE, RCAState.ERROR],
            RCAState.ITERATION_COMPLETE: [RCAState.QUESTIONING, RCAState.ANALYSIS_COMPLETE, RCAState.ERROR],
            RCAState.ANALYSIS_COMPLETE: [],
            RCAState.ERROR: []
        }
        
        return new_state in valid_transitions.get(self.current_state, [])
    
    def should_continue_iteration(self) -> bool:
        """Check if should continue to next iteration"""
        if self.current_depth >= self.max_depth:
            return False
        if self.mode == "NO_FMEA_SINGLE_SHOT" and self.current_depth >= 1:
            return False
        if self.stop_reason is not None:
            return False
        return True


class LLMContextManager:
    """Manages what context LLM receives - orchestrator controlled"""
    
    @staticmethod
    def create_question_context(
        complaint: str,
        execution_memory: ExecutionMemory,
        current_depth: int
    ) -> str:
        """Create controlled context for LLM question generation"""
        
        if current_depth == 1:
            # First question - only complaint
            return f"COMPLAINT: {complaint}"
        
        # Subsequent questions - curated context only
        if not execution_memory.iterations:
            return f"COMPLAINT: {complaint}"
        
        # Get last iteration only (not full history)
        last_iteration = execution_memory.iterations[-1]
        
        context = f"""ORIGINAL COMPLAINT: {complaint}

PREVIOUS ANALYSIS:
Question: {last_iteration.question}
Selected Cause: {last_iteration.selected_cause.get('cause_text', 'None') if last_iteration.selected_cause else 'None'}

Generate the next "Why?" question to dig deeper into this cause."""
        
        return context
    
    @staticmethod
    def create_cause_ranking_context(
        question: str,
        causes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create controlled context for cause ranking"""
        return {
            "question": question,
            "causes": causes[:10],  # Limit to top 10 causes
            "total_causes": len(causes)
        }


class RCAStateMachine:
    """Central state machine for RCA analysis"""
    
    def __init__(self, complaint_id: str, complaint: str, **kwargs):
        self.complaint_id = complaint_id
        self.complaint = complaint
        self.evidence = kwargs.get('evidence', '')
        self.sop = kwargs.get('sop', '')
        self.fmea_document_path = kwargs.get('fmea_document_path')
        
        # Evidence and investigation data
        self.evidence_files = kwargs.get('evidence_files', [])
        self.logs = kwargs.get('logs')
        self.reports = kwargs.get('reports')
        self.process_data = kwargs.get('process_data')
        self.historical_capa = kwargs.get('historical_capa')
        self.policies = kwargs.get('policies')
        self.investigation_records = kwargs.get('investigation_records')
        self.supporting_system_information = kwargs.get('supporting_system_information')
        
        # Initialize memories
        self.execution_memory = ExecutionMemory()
        self.control_memory = ControlMemory(
            max_depth=kwargs.get('max_depth', 100),  # Default to 100 (effectively unlimited)
            mode="FMEA_ITERATIVE" if self.fmea_document_path else "NO_FMEA_SINGLE_SHOT"
        )
        
        # Context manager
        self.context_manager = LLMContextManager()
    
    def transition_to(self, new_state: RCAState, reason: str = "") -> bool:
        """Controlled state transition"""
        if not self.control_memory.can_transition_to(new_state):
            return False
        
        old_state = self.control_memory.current_state
        self.control_memory.current_state = new_state
        
        # Log transition
        self.execution_memory.log_state_transition(old_state, new_state, reason)
        
        return True
    
    def get_current_state(self) -> RCAState:
        """Get current state"""
        return self.control_memory.current_state
    
    def should_continue(self) -> bool:
        """Check if analysis should continue"""
        return (
            self.control_memory.current_state not in [RCAState.ANALYSIS_COMPLETE, RCAState.ERROR] and
            self.control_memory.should_continue_iteration()
        )
    
    def get_llm_context_for_question(self) -> str:
        """Get controlled context for LLM question generation"""
        return self.context_manager.create_question_context(
            self.complaint,
            self.execution_memory,
            self.control_memory.current_depth + 1
        )
    
    def get_llm_context_for_ranking(self, question: str, causes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get controlled context for LLM cause ranking"""
        return self.context_manager.create_cause_ranking_context(question, causes)
    
    def start_new_iteration(self):
        """Start new iteration - update control state"""
        self.control_memory.current_depth += 1
        self.transition_to(RCAState.QUESTIONING, f"Starting iteration {self.control_memory.current_depth}")
    
    def complete_iteration(self, iteration: IterationMemory):
        """Complete iteration - update memories"""
        self.execution_memory.add_iteration(iteration)
        
        # Update final root cause
        if iteration.selected_cause:
            self.control_memory.final_root_cause = iteration.selected_cause
        
        # Check stopping conditions
        if not iteration.causes_found:
            self.control_memory.stop_reason = StopReason.NO_CAUSES_FOUND
            self.transition_to(RCAState.ANALYSIS_COMPLETE, "No causes found")
        elif self.control_memory.current_depth >= self.control_memory.max_depth:
            self.control_memory.stop_reason = StopReason.MAX_DEPTH_REACHED
            self.transition_to(RCAState.ANALYSIS_COMPLETE, "Max depth reached")
        elif self.control_memory.mode == "NO_FMEA_SINGLE_SHOT":
            self.control_memory.stop_reason = StopReason.SINGLE_SHOT_COMPLETE
            self.transition_to(RCAState.ANALYSIS_COMPLETE, "Single shot complete")
        elif self._detect_cause_repetition():
            self.control_memory.stop_reason = StopReason.CAUSE_REPETITION
            self.transition_to(RCAState.ANALYSIS_COMPLETE, "Cause repetition detected")
        else:
            self.transition_to(RCAState.ITERATION_COMPLETE, "Iteration completed successfully")
    
    def _detect_cause_repetition(self) -> bool:
        """Detect if causes are repeating"""
        if len(self.execution_memory.iterations) < 2:
            return False
        
        # Check last 2 iterations
        recent_causes = []
        for iteration in self.execution_memory.iterations[-2:]:
            if iteration.selected_cause:
                recent_causes.append(iteration.selected_cause.get('cause_text', '').strip().lower())
        
        return len(set(recent_causes)) == 1 and len(recent_causes) == 2
    
    def get_final_result(self) -> Dict[str, Any]:
        """Generate final result from state machine"""
        # Determine confidence
        confidence = "HIGH"
        if self.control_memory.mode == "NO_FMEA_SINGLE_SHOT":
            confidence = "MEDIUM"
        elif not self.control_memory.final_root_cause:
            confidence = "LOW"
        elif self.control_memory.current_depth < 2:
            confidence = "MEDIUM"
        
        # Build root cause detail
        root_cause_detail = None
        if self.control_memory.final_root_cause:
            rc = self.control_memory.final_root_cause
            root_cause_detail = {
                "cause_id": rc.get("cause_id", "UNKNOWN"),
                "cause_text": rc.get("cause_text", ""),
                "process_step": rc.get("process_step", ""),
                "failure_mode": rc.get("failure_mode"),
                "potential_effects": rc.get("potential_effects"),
                "severity": rc.get("severity"),
                "occurrence": rc.get("occurrence"),
                "detection": rc.get("detection"),
                "current_controls": rc.get("current_controls"),
                "source": rc.get("source", "FMEA"),
                "reason": rc.get("reason", "Selected as most critical cause"),
                "confidence_score": rc.get("confidence_score", 0.8)
            }
        
        # Convert iterations to output format
        why_iterations = []
        for iteration in self.execution_memory.iterations:
            # Convert causes to output format
            causes_output = []
            for cause in iteration.causes_found:
                cause_dict = {
                    "cause_id": cause.get("cause_id", "UNKNOWN"),
                    "cause_text": cause.get("cause_text", ""),
                    "process_step": cause.get("process_step", ""),
                    "failure_mode": cause.get("failure_mode"),
                    "potential_effects": cause.get("potential_effects"),
                    "severity": cause.get("severity"),
                    "occurrence": cause.get("occurrence"),
                    "detection": cause.get("detection"),
                    "current_controls": cause.get("current_controls"),
                    "source": cause.get("source", "FMEA")
                }
                
                # Add category fields if present (depth 1 only)
                if "category" in cause:
                    cause_dict["category"] = cause.get("category")
                    cause_dict["category_confidence"] = cause.get("category_confidence")
                    cause_dict["category_reasoning"] = cause.get("category_reasoning")
                    cause_dict["secondary_categories"] = cause.get("secondary_categories", [])
                
                causes_output.append(cause_dict)
            
            # Convert selected cause
            selected_cause_output = None
            if iteration.selected_cause:
                sc = iteration.selected_cause
                selected_cause_output = {
                    "cause_id": sc.get("cause_id", "UNKNOWN"),
                    "cause_text": sc.get("cause_text", ""),
                    "process_step": sc.get("process_step", ""),
                    "failure_mode": sc.get("failure_mode"),
                    "potential_effects": sc.get("potential_effects"),
                    "severity": sc.get("severity"),
                    "occurrence": sc.get("occurrence"),
                    "detection": sc.get("detection"),
                    "current_controls": sc.get("current_controls"),
                    "source": sc.get("source", "FMEA")
                }
            
            why_iterations.append({
                "depth": iteration.depth,
                "question": iteration.question,
                "reasoning": f"Generated question for depth {iteration.depth}",
                "causes_found": len(iteration.causes_found),
                "causes": causes_output,
                "selected_cause": selected_cause_output,
                "selection_justification": iteration.selection_justification,
                "fmea_matches": iteration.fmea_matches,
                "generation_method": iteration.generation_method
            })
        
        # Error message
        error_msg = None
        if not self.control_memory.final_root_cause and self.control_memory.stop_reason:
            if self.control_memory.stop_reason == StopReason.NO_CAUSES_FOUND:
                error_msg = "No causes could be identified for the given complaint"
            elif self.control_memory.stop_reason == StopReason.CAUSE_REPETITION:
                error_msg = "Analysis stopped - same cause repeated, no deeper root cause available"
            elif self.control_memory.stop_reason == StopReason.MAX_DEPTH_REACHED:
                error_msg = "Analysis stopped - maximum depth reached"
            elif self.control_memory.stop_reason == StopReason.FMEA_EXHAUSTED:
                error_msg = "FMEA exhausted - no more causes available, using last selected cause as root cause"
            else:
                error_msg = "No root cause could be determined"
        
        return {
            "complaint_id": self.complaint_id,
            "root_cause": root_cause_detail,
            "confidence": confidence,
            "mode": self.control_memory.mode,
            "analysis_depth": self.control_memory.current_depth,
            "why_iterations": why_iterations,
            "total_causes_analyzed": self.execution_memory.total_causes_analyzed,
            "fmea_document_used": self.fmea_document_path,
            "execution_time_seconds": round(self.execution_memory.get_execution_time(), 2),
            "stopping_reason": self.control_memory.stop_reason.value if self.control_memory.stop_reason else "completed",
            "error": error_msg
        }