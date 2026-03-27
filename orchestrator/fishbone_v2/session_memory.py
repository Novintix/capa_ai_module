"""
Session Memory Manager for Fishbone v2
Redis-backed session management per complaint_id
"""

import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import redis
from .logger import log_error, log_memory_update


@dataclass
class SessionIteration:
    """Single iteration in session memory"""
    depth: int
    causes_evaluated: List[str]  # List of cause_ids evaluated
    selected_cause_id: str
    selected_cause_text: str
    validation_confidence: float
    timestamp: float


@dataclass
class SessionState:
    """Complete session state for a complaint_id"""
    complaint_id: str
    complaint: str
    evidence: str
    sop: str
    fmea_document_path: Optional[str]
    
    # Session tracking
    session_start_time: float
    last_updated: float
    iterations: List[SessionIteration]
    
    # Evaluated causes tracking (prevents re-evaluation)
    all_evaluated_cause_ids: List[str]
    all_evaluated_cause_texts: List[str]  # Normalized lowercase
    
    # Current state
    current_depth: int
    is_complete: bool
    final_root_cause_id: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        return {
            "complaint_id": self.complaint_id,
            "complaint": self.complaint,
            "evidence": self.evidence,
            "sop": self.sop,
            "fmea_document_path": self.fmea_document_path,
            "session_start_time": self.session_start_time,
            "last_updated": self.last_updated,
            "iterations": [
                {
                    "depth": it.depth,
                    "causes_evaluated": it.causes_evaluated,
                    "selected_cause_id": it.selected_cause_id,
                    "selected_cause_text": it.selected_cause_text,
                    "validation_confidence": it.validation_confidence,
                    "timestamp": it.timestamp
                }
                for it in self.iterations
            ],
            "all_evaluated_cause_ids": self.all_evaluated_cause_ids,
            "all_evaluated_cause_texts": self.all_evaluated_cause_texts,
            "current_depth": self.current_depth,
            "is_complete": self.is_complete,
            "final_root_cause_id": self.final_root_cause_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary"""
        iterations = [
            SessionIteration(
                depth=it["depth"],
                causes_evaluated=it["causes_evaluated"],
                selected_cause_id=it["selected_cause_id"],
                selected_cause_text=it["selected_cause_text"],
                validation_confidence=it["validation_confidence"],
                timestamp=it["timestamp"]
            )
            for it in data.get("iterations", [])
        ]
        
        return cls(
            complaint_id=data["complaint_id"],
            complaint=data["complaint"],
            evidence=data.get("evidence", ""),
            sop=data.get("sop", ""),
            fmea_document_path=data.get("fmea_document_path"),
            session_start_time=data["session_start_time"],
            last_updated=data["last_updated"],
            iterations=iterations,
            all_evaluated_cause_ids=data.get("all_evaluated_cause_ids", []),
            all_evaluated_cause_texts=data.get("all_evaluated_cause_texts", []),
            current_depth=data.get("current_depth", 0),
            is_complete=data.get("is_complete", False),
            final_root_cause_id=data.get("final_root_cause_id")
        )


class SessionMemoryManager:
    """
    Manages session-based memory for Fishbone v2
    
    Key Features:
    - Per-complaint_id session isolation
    - Redis persistence for session continuity
    - Tracks all evaluated causes to prevent re-evaluation
    - Supports session resume and continuation
    - Automatic session expiry (7 days)
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl_seconds: int = 604800):
        """
        Initialize session memory manager
        
        Args:
            redis_url: Redis connection URL
            ttl_seconds: Session TTL in seconds (default: 7 days)
        """
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            self.ttl_seconds = ttl_seconds
            log_memory_update("session_memory", "init", "connect", "Redis connected successfully")
        except Exception as e:
            log_error("SessionMemoryManager.__init__", f"Redis connection failed: {str(e)}")
            raise ValueError(f"Redis connection failed: {str(e)}")
    
    def _get_session_key(self, complaint_id: str) -> str:
        """Get Redis key for session"""
        return f"fishbone_v2:session:{complaint_id}"
    
    def get_session(self, complaint_id: str) -> Optional[SessionState]:
        """Get existing session state"""
        try:
            key = self._get_session_key(complaint_id)
            data = self.redis_client.get(key)
            
            if not data:
                return None
            
            session_dict = json.loads(data)
            session = SessionState.from_dict(session_dict)
            
            log_memory_update("session_memory", complaint_id, "retrieve", f"Session found with {len(session.iterations)} iterations")
            
            return session
            
        except Exception as e:
            log_error("get_session", f"Failed to retrieve session for {complaint_id}: {str(e)}")
            return None
    
    def create_session(
        self,
        complaint_id: str,
        complaint: str,
        evidence: str = "",
        sop: str = "",
        fmea_document_path: Optional[str] = None
    ) -> SessionState:
        """Create new session state"""
        session = SessionState(
            complaint_id=complaint_id,
            complaint=complaint,
            evidence=evidence,
            sop=sop,
            fmea_document_path=fmea_document_path,
            session_start_time=time.time(),
            last_updated=time.time(),
            iterations=[],
            all_evaluated_cause_ids=[],
            all_evaluated_cause_texts=[],
            current_depth=0,
            is_complete=False,
            final_root_cause_id=None
        )
        
        self.save_session(session)
        
        log_memory_update("session_memory", complaint_id, "create", "New session created")
        
        return session
    
    def save_session(self, session: SessionState):
        """Save session state to Redis"""
        try:
            key = self._get_session_key(session.complaint_id)
            session.last_updated = time.time()
            
            data = json.dumps(session.to_dict())
            self.redis_client.setex(key, self.ttl_seconds, data)
            
            log_memory_update(
                "session_memory",
                session.complaint_id,
                "save",
                f"Session saved with {len(session.iterations)} iterations"
            )
            
        except Exception as e:
            log_error("save_session", f"Failed to save session for {session.complaint_id}: {str(e)}")
    
    def add_iteration(
        self,
        session: SessionState,
        causes_evaluated: List[Dict[str, Any]],
        selected_cause: Dict[str, Any],
        validation_confidence: float
    ):
        """Add iteration to session and update evaluated causes"""
        # Extract cause IDs and texts
        cause_ids = [c.get("cause_id", "") for c in causes_evaluated]
        cause_texts = [c.get("cause_text", "").lower().strip() for c in causes_evaluated]
        
        # Create iteration
        iteration = SessionIteration(
            depth=session.current_depth + 1,
            causes_evaluated=cause_ids,
            selected_cause_id=selected_cause.get("cause_id", ""),
            selected_cause_text=selected_cause.get("cause_text", ""),
            validation_confidence=validation_confidence,
            timestamp=time.time()
        )
        
        # Update session
        session.iterations.append(iteration)
        session.current_depth += 1
        
        # Update evaluated causes (for duplicate prevention)
        session.all_evaluated_cause_ids.extend(cause_ids)
        session.all_evaluated_cause_texts.extend(cause_texts)
        
        # Save
        self.save_session(session)
        
        log_memory_update(
            "session_memory",
            session.complaint_id,
            "add_iteration",
            f"Iteration {session.current_depth} added, {len(cause_ids)} causes evaluated"
        )
    
    def mark_complete(self, session: SessionState, final_root_cause_id: str):
        """Mark session as complete"""
        session.is_complete = True
        session.final_root_cause_id = final_root_cause_id
        self.save_session(session)
        
        log_memory_update(
            "session_memory",
            session.complaint_id,
            "complete",
            f"Session marked complete with root cause: {final_root_cause_id}"
        )
    
    def is_cause_already_evaluated(self, session: SessionState, cause: Dict[str, Any]) -> bool:
        """Check if cause was already evaluated in this session"""
        cause_text = cause.get("cause_text", "").lower().strip()
        
        # Check by EXACT text match only
        if cause_text:
            for evaluated_text in session.all_evaluated_cause_texts:
                if cause_text == evaluated_text:
                    return True
        
        return False
    
    def filter_unevaluated_causes(self, session: SessionState, causes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out causes that were already evaluated"""
        unevaluated = []
        
        for cause in causes:
            if not self.is_cause_already_evaluated(session, cause):
                unevaluated.append(cause)
        
        filtered_count = len(causes) - len(unevaluated)
        if filtered_count > 0:
            log_memory_update(
                "session_memory",
                session.complaint_id,
                "filter",
                f"Filtered {filtered_count} already-evaluated causes"
            )
        
        return unevaluated
    
    def delete_session(self, complaint_id: str):
        """Delete session (for cleanup or reset)"""
        try:
            key = self._get_session_key(complaint_id)
            self.redis_client.delete(key)
            
            log_memory_update("session_memory", complaint_id, "delete", "Session deleted")
            
        except Exception as e:
            log_error("delete_session", f"Failed to delete session for {complaint_id}: {str(e)}")
