"""
Session memory manager for Root Cause Analysis coordinator.
"""

import json
import time
from typing import Any, Dict, Optional

try:
    import redis
except Exception:
    redis = None

try:
    from config.redis_config import REDIS_URL
except Exception:
    REDIS_URL = "redis://localhost:6379"

from .logger import log_error, log_info


class RCASessionMemoryManager:
    """
    Redis-backed session memory with in-process fallback.
    """

    def __init__(self, redis_url: str = REDIS_URL, ttl_seconds: int = 604800):
        self.ttl_seconds = ttl_seconds
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._redis_client = None

        if redis is None:
            log_info("Redis package not available. Using in-memory RCA sessions.")
            return

        try:
            self._redis_client = redis.from_url(redis_url, decode_responses=True)
            self._redis_client.ping()
            log_info("RCA session memory connected to Redis")
        except Exception as exc:
            self._redis_client = None
            log_error("session_memory_init", str(exc))
            log_info("Falling back to in-memory RCA sessions")

    @staticmethod
    def _session_key(complaint_id: str) -> str:
        return f"root_cause_analysis:session:{complaint_id}"

    def save_state(self, complaint_id: str, state_data: Dict[str, Any]) -> None:
        state_data = dict(state_data)
        state_data["updated_at"] = time.time()

        if self._redis_client is not None:
            try:
                key = self._session_key(complaint_id)
                self._redis_client.setex(key, self.ttl_seconds, json.dumps(state_data, default=str))
                return
            except Exception as exc:
                log_error("save_state", str(exc), complaint_id)

        self._memory_store[complaint_id] = state_data

    def get_state(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        if self._redis_client is not None:
            try:
                key = self._session_key(complaint_id)
                value = self._redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as exc:
                log_error("get_state", str(exc), complaint_id)

        return self._memory_store.get(complaint_id)

    def delete_state(self, complaint_id: str) -> None:
        if self._redis_client is not None:
            try:
                key = self._session_key(complaint_id)
                self._redis_client.delete(key)
            except Exception as exc:
                log_error("delete_state", str(exc), complaint_id)

        self._memory_store.pop(complaint_id, None)
