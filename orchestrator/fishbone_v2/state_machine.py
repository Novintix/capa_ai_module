"""
Fishbone v2 State Machine
Production-grade state management with controlled memory
Single depth analysis only - no iteration loops
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time


class FishboneState(Enum):
    """Defined states for Fishbone v2 analysis"""
    INITIALIZING = "initializing"
    LISTING_CAUSES = "listing_causes"
    CATEGORIZING = "categorizing"
    VALIDATING = "validating"
    ROUTING_DECISION = "routing_decision"
    ZERO_EVIDENCE = "zero_evidence"
    RANKING = "ranking"
    ANALYSIS_COMPLETE = "analysis_complete"
    ERROR = "error"


class StopReason(Enum):
    """Reasons for stopping analysis"""
    COMPLETED = "completed"
    NO_CAUSES_FOUND = "no_causes_found"
    SINGLE_SHOT_COMPLETE = "single_shot_complete"
    ALL_CAUSES_EVALUATED = "all_causes_evaluated"
    ERROR_OCCURRED = "error_occurred"
    INVALID_INPUT = "invalid_input"


@dataclass
class IterationMemory:
    """Memory for the single iteration"""
    depth: int
    causes_found: List[Dict[str, Any]]
    categorized_causes: List[Dict[str, Any]]
    validated_causes: List[Dict[str, Any]]
    selected_cause: Optional[Dict[str, Any]]
    fmea_matches: int
    generation_method: str
    validation_confidence: float = 0.0
    high_confidence_count: int = 0
    category_summary: Optional[Dict[str, int]] = None
    selection_justification: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionMemory:
    """Complete execution history - orchestrator only"""
    iteration: Optional[IterationMemory] = None
    total_causes_analyzed: int = 0
    start_time: float = field(default_factory=time.time)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_iteration(self, iteration: IterationMemory):
        """Set the single iteration"""
        self.iteration = iteration
        self.total_causes_analyzed = len(iteration.causes_found)
    
    def get_execution_time(self) -> float:
        """Get total execution time"""
        return time.time() - self.start_time
    
    def log_state_transition(self, from_state, to_state, reason: str):
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
    current_state = None  # Will be set to FishboneState.INITIALIZING
    current_depth: int = 0
    max_depth: int = 1  # SINGLE DEPTH ONLY
    mode: str = "SINGLE_SHOT"
    stop_reason: Optional[StopReason] = None
    confidence_level: str = "MEDIUM"
    final_root_cause: Optional[Dict[str, Any]] = None
    execution_trace: List[str] = None  # Track agent execution
    
    def __post_init__(self):
        if self.execution_trace is None:
            self.execution_trace = []
    
    def can_transition_to(self, new_state) -> bool:
        """Validate state transition"""
        from .state_machine import FishboneState
        
        valid_transitions = {
            FishboneState.INITIALIZING: [FishboneState.LISTING_CAUSES, FishboneState.ERROR],
            FishboneState.LISTING_CAUSES: [FishboneState.CATEGORIZING, FishboneState.ANALYSIS_COMPLETE, FishboneState.ERROR],
            FishboneState.CATEGORIZING: [FishboneState.VALIDATING, FishboneState.ERROR],
            FishboneState.VALIDATING: [FishboneState.ROUTING_DECISION, FishboneState.ERROR],
            FishboneState.ROUTING_DECISION: [FishboneState.ZERO_EVIDENCE, FishboneState.RANKING, FishboneState.ANALYSIS_COMPLETE, FishboneState.ERROR],
            FishboneState.ZERO_EVIDENCE: [FishboneState.ANALYSIS_COMPLETE, FishboneState.ERROR],
            FishboneState.RANKING: [FishboneState.ANALYSIS_COMPLETE, FishboneState.ERROR],
            FishboneState.ANALYSIS_COMPLETE: [],
            FishboneState.ERROR: []
        }
        
        return new_state in valid_transitions.get(self.current_state, [])
    
    def should_continue_iteration(self) -> bool:
        """Check if should continue - ALWAYS FALSE (single depth only)"""
        return False


class FishboneStateMachine:
    """Central state machine for Fishbone v2 analysis - Single Depth Only"""
    
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
        self.control_memory = ControlMemory()
        self.control_memory.current_state = FishboneState.INITIALIZING
        self.control_memory.max_depth = 1
        self.control_memory.mode = "SINGLE_SHOT"
    
    def transition_to(self, new_state: FishboneState, reason: str = "") -> bool:
        """Controlled state transition"""
        if not self.control_memory.can_transition_to(new_state):
            return False
        
        old_state = self.control_memory.current_state
        self.control_memory.current_state = new_state
        
        # Log transition
        self.execution_memory.log_state_transition(old_state, new_state, reason)
        
        return True
    
    def get_current_state(self) -> FishboneState:
        """Get current state"""
        return self.control_memory.current_state
    
    def should_continue(self) -> bool:
        """Check if analysis should continue - ALWAYS FALSE after first iteration"""
        return (
            self.control_memory.current_state not in [FishboneState.ANALYSIS_COMPLETE, FishboneState.ERROR] and
            self.control_memory.current_depth < 1
        )
    
    def start_iteration(self):
        """Start the single iteration"""
        self.control_memory.current_depth = 1
        self.transition_to(FishboneState.LISTING_CAUSES, "Starting single depth analysis")
    
    def complete_iteration(self, iteration: IterationMemory):
        """Complete the single iteration"""
        self.execution_memory.set_iteration(iteration)
        
        # Update final root cause
        if iteration.selected_cause:
            self.control_memory.final_root_cause = iteration.selected_cause
        
        # Always stop after single iteration
        self.control_memory.stop_reason = StopReason.SINGLE_SHOT_COMPLETE
        self.transition_to(FishboneState.ANALYSIS_COMPLETE, "Single depth analysis complete")
    
    def get_final_result(self) -> Dict[str, Any]:
        """Generate final result from state machine"""
        # Determine confidence
        confidence = "MEDIUM"
        if not self.control_memory.final_root_cause:
            confidence = "LOW"
        elif self.execution_memory.iteration and self.execution_memory.iteration.high_confidence_count > 0:
            confidence = "HIGH"
        
        # Build root cause detail
        root_cause_detail = None
        if self.control_memory.final_root_cause:
            rc = self.control_memory.final_root_cause
            rc_pe = rc.get("potential_effects")
            rc_fm = rc.get("failure_mode")
            rc_cc = rc.get("current_controls")
            root_cause_detail = {
                "cause_id": rc.get("cause_id", "UNKNOWN"),
                "cause_text": rc.get("cause_text", ""),
                "process_step": rc.get("process_step", ""),
                "category": rc.get("category"),
                "category_confidence": rc.get("category_confidence"),
                "failure_mode": rc_fm if isinstance(rc_fm, str) else None,
                "potential_effects": rc_pe if isinstance(rc_pe, str) else None,
                "severity": rc.get("severity"),
                "occurrence": rc.get("occurrence"),
                "detection": rc.get("detection"),
                "current_controls": rc_cc if isinstance(rc_cc, str) else None,
                "source": rc.get("source", "FMEA"),
                "reason": rc.get("reason", "Selected as most critical cause"),
                "confidence_score": rc.get("confidence_score", 0.8),
                "selection_justification": rc.get("selection_justification", ""),
                "validation_status": rc.get("validation_status"),
                "validation_confidence": rc.get("validation_confidence", 0.0)
            }
        
        # Convert iteration to output format
        causes_output = []
        category_summary = None
        validated_count = 0
        high_conf_count = 0
        
        if self.execution_memory.iteration:
            it = self.execution_memory.iteration
            category_summary = it.category_summary
            validated_count = len(it.validated_causes)
            high_conf_count = it.high_confidence_count
            
            for cause in it.categorized_causes:
                pe = cause.get("potential_effects")
                fm = cause.get("failure_mode")
                cc = cause.get("current_controls")
                causes_output.append({
                    "cause_id": cause.get("cause_id", "UNKNOWN"),
                    "cause_text": cause.get("cause_text", ""),
                    "process_step": cause.get("process_step", ""),
                    "category": cause.get("category"),
                    "category_confidence": cause.get("category_confidence"),
                    "category_reasoning": cause.get("category_reasoning"),
                    "secondary_categories": cause.get("secondary_categories", []),
                    "failure_mode": fm if isinstance(fm, str) else None,
                    "potential_effects": pe if isinstance(pe, str) else None,
                    "severity": cause.get("severity"),
                    "occurrence": cause.get("occurrence"),
                    "detection": cause.get("detection"),
                    "current_controls": cc if isinstance(cc, str) else None,
                    "source": cause.get("source", "FMEA"),
                    "validation_status": cause.get("validation_status"),
                    "validation_confidence": cause.get("validation_confidence")
                })
        
        # Error message
        error_msg = None
        if not self.control_memory.final_root_cause and self.control_memory.stop_reason:
            if self.control_memory.stop_reason == StopReason.NO_CAUSES_FOUND:
                error_msg = "No causes could be identified for the given complaint"
            else:
                error_msg = "No root cause could be determined"
        
        return {
            "complaint_id": self.complaint_id,
            "root_cause": root_cause_detail,
            "confidence": confidence,
            "mode": self.control_memory.mode,
            "causes_found": len(causes_output),
            "causes": causes_output,
            "category_summary": category_summary,
            "validated_causes_count": validated_count,
            "high_confidence_causes_count": high_conf_count,
            "fmea_document_used": self.fmea_document_path,
            "execution_time_seconds": round(self.execution_memory.get_execution_time(), 2),
            "stopping_reason": self.control_memory.stop_reason.value if self.control_memory.stop_reason else "completed",
            "error": error_msg,
            "execution_trace": self.control_memory.execution_trace
        }
