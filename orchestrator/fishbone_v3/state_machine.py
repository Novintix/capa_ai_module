"""
Fishbone v3 State Machine
Production-grade state management with HITL support
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time


class FishboneV3State(Enum):
    """Defined states for Fishbone v3 analysis"""
    INITIALIZING = "initializing"
    LISTING_CAUSES = "listing_causes"
    CATEGORIZING = "categorizing"
    VALIDATING = "validating"
    WAIT_FOR_HUMAN = "wait_for_human"
    RECORDING_DECISIONS = "recording_decisions"
    ANALYSIS_COMPLETE = "analysis_complete"
    ERROR = "error"


class StopReason(Enum):
    """Reasons for stopping analysis"""
    COMPLETED = "completed"
    NO_CAUSES_FOUND = "no_causes_found"
    HITL_PENDING = "hitl_pending"
    HITL_COMPLETE = "hitl_complete"
    ERROR_OCCURRED = "error_occurred"
    INVALID_INPUT = "invalid_input"


@dataclass
class IterationMemory:
    """Memory for the analysis phase"""
    causes_found: List[Dict[str, Any]] = field(default_factory=list)
    categorized_causes: List[Dict[str, Any]] = field(default_factory=list)
    validated_causes: List[Dict[str, Any]] = field(default_factory=list)
    category_summary: Optional[Dict[str, int]] = None
    validation_confidence: float = 0.0
    zero_evidence_result: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionMemory:
    """Complete execution history"""
    iteration: Optional[IterationMemory] = None
    start_time: float = field(default_factory=time.time)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    
    def log_state_transition(self, from_state, to_state, reason: str):
        """Log state transition"""
        self.state_transitions.append({
            "from": from_state.value if from_state else None,
            "to": to_state.value if to_state else None,
            "reason": reason,
            "timestamp": time.time()
        })


@dataclass
class ControlMemory:
    """Control state and decisions"""
    current_state: FishboneV3State = FishboneV3State.INITIALIZING
    stop_reason: Optional[StopReason] = None
    execution_trace: List[str] = field(default_factory=list)
    
    def can_transition_to(self, new_state: FishboneV3State) -> bool:
        """Validate state transition for V3"""
        valid_transitions = {
            FishboneV3State.INITIALIZING: [FishboneV3State.LISTING_CAUSES, FishboneV3State.ERROR],
            FishboneV3State.LISTING_CAUSES: [FishboneV3State.CATEGORIZING, FishboneV3State.ERROR],
            FishboneV3State.CATEGORIZING: [FishboneV3State.VALIDATING, FishboneV3State.ERROR],
            FishboneV3State.VALIDATING: [FishboneV3State.WAIT_FOR_HUMAN, FishboneV3State.ERROR],
            FishboneV3State.WAIT_FOR_HUMAN: [FishboneV3State.RECORDING_DECISIONS, FishboneV3State.ERROR],
            FishboneV3State.RECORDING_DECISIONS: [FishboneV3State.ANALYSIS_COMPLETE, FishboneV3State.ERROR],
            FishboneV3State.ANALYSIS_COMPLETE: [],
            FishboneV3State.ERROR: []
        }
        return new_state in valid_transitions.get(self.current_state, [])


class FishboneV3StateMachine:
    """Central state machine for Fishbone v3 analysis with HITL"""
    
    def __init__(self, complaint_id: str, complaint: str, **kwargs):
        self.complaint_id = complaint_id
        self.complaint = complaint
        self.kwargs = kwargs
        
        # Initialize memories
        self.execution_memory = ExecutionMemory()
        self.control_memory = ControlMemory()
        self.control_memory.current_state = FishboneV3State.INITIALIZING
    
    def transition_to(self, new_state: FishboneV3State, reason: str = "") -> bool:
        """Controlled state transition"""
        if not self.control_memory.can_transition_to(new_state):
            # Allow jumping to ERROR from anywhere if not explicitly in transitions
            if new_state != FishboneV3State.ERROR:
                return False
        
        old_state = self.control_memory.current_state
        self.control_memory.current_state = new_state
        self.execution_memory.log_state_transition(old_state, new_state, reason)
        return True

    def get_final_result(self) -> Dict[str, Any]:
        """Generate result for the current status (either pending human or complete)"""
        it = self.execution_memory.iteration or IterationMemory()
        
        # Map state to status string
        status_map = {
            FishboneV3State.WAIT_FOR_HUMAN: "WAIT_FOR_HUMAN",
            FishboneV3State.ANALYSIS_COMPLETE: "COMPLETED",
            FishboneV3State.ERROR: "ERROR"
        }
        status = status_map.get(self.control_memory.current_state, "IN_PROGRESS")
        
        # Calculate statistics
        total_causes = len(it.causes_found)
        all_categorized = it.categorized_causes
        validated_count = len(it.validated_causes)
        
        # Separate high and low confidence causes
        # High confidence = validation_confidence >= 0.9 AND validation_status == "matched"
        high_confidence = [
            c for c in all_categorized 
            if c.get("validation_confidence", 0.0) >= 0.9 
            and c.get("validation_status") == "matched"
        ]
        low_confidence = [
            c for c in all_categorized 
            if c.get("validation_confidence", 0.0) < 0.9 
            or c.get("validation_status") != "matched"
        ]

        return {
            "complaint_id": self.complaint_id,
            "status": status,
            "mode": "HITL_V3",
            "total_causes_found": total_causes,
            "causes_validated_with_evidence": validated_count,
            "high_confidence_causes_count": len(high_confidence),
            "low_confidence_causes_count": len(low_confidence),
            
            # Detailed breakdown by stage
            "all_causes_found": it.causes_found,
            "all_categorized_causes": all_categorized,
            "all_validated_causes": it.validated_causes,
            "high_confidence_causes": high_confidence,
            "low_confidence_causes": low_confidence,
            
            # Zero Evidence Agent result (if executed)
            "zero_evidence_result": it.zero_evidence_result,
            
            # Legacy fields
            "causes_found": len(it.categorized_causes),
            "causes": it.categorized_causes,
            "category_summary": it.category_summary,
            "validated_causes_count": validated_count,
            "execution_time_seconds": round(time.time() - self.execution_memory.start_time, 2),
            "stopping_reason": self.control_memory.stop_reason.value if self.control_memory.stop_reason else None,
            "execution_trace": self.control_memory.execution_trace
        }
