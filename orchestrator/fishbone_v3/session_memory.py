"""
Session Memory Manager for Fishbone v3
Redis-backed session management with HITL state persistence
"""

import json
import time
from typing import Dict, Any, List, Optional
import redis
from .logger import log_error, log_memory_update


class SessionMemoryManagerV3:
    """
    Manages session-based memory for Fishbone v3 (HITL)
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl_seconds: int = 604800):
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            self.ttl_seconds = ttl_seconds
            log_memory_update("session_memory_v3", "init", "connect", "Redis connected")
        except Exception as e:
            log_error("SessionMemoryManagerV3.__init__", f"Redis connection failed: {str(e)}")
            raise ValueError(f"Redis connection failed: {str(e)}")
    
    def _get_session_key(self, complaint_id: str) -> str:
        return f"fishbone_v3:session:{complaint_id}"
    
    def save_state(self, complaint_id: str, state_data: Dict[str, Any]):
        """Save the entire analysis state to Redis"""
        try:
            key = self._get_session_key(complaint_id)
            data = json.dumps(state_data)
            self.redis_client.setex(key, self.ttl_seconds, data)
            log_memory_update("session_memory_v3", complaint_id, "save_state", "State saved to Redis")
        except Exception as e:
            log_error("save_state", f"Failed to save state for {complaint_id}: {str(e)}")

    def get_state(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the analysis state from Redis"""
        try:
            key = self._get_session_key(complaint_id)
            data = self.redis_client.get(key)
            if data:
                log_memory_update("session_memory_v3", complaint_id, "get_state", "State retrieved from Redis")
                return json.loads(data)
            return None
        except Exception as e:
            log_error("get_state", f"Failed to retrieve state for {complaint_id}: {str(e)}")
            return None

    def delete_session(self, complaint_id: str):
        """Delete session data"""
        try:
            key = self._get_session_key(complaint_id)
            self.redis_client.delete(key)
            log_memory_update("session_memory_v3", complaint_id, "delete", "Session deleted")
        except Exception as e:
            log_error("delete_session", f"Failed to delete session for {complaint_id}: {str(e)}")
