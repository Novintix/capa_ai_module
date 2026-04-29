import os
import json
import datetime
import redis
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# The URL from .env (e.g., redis://localhost:6379)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# A pre-configured Redis client object
# decode_responses=False is REQUIRED for LangGraph checkpointing
redis_client = redis.from_url(REDIS_URL, decode_responses=False)

# Re-use this everywhere to avoid multiple connection pools
def get_redis_client():
    return redis_client


# ── Agent status helpers ──────────────────────────────────────────────────────
# Hash key:   agent_status:{thread_id}
#   field:    {node_name}
#   value:    JSON  {"status": "running"|"done"|"error", "ts": "<iso>"}
#
# Pub/Sub channel:  agent_events:{thread_id}
#   message:  JSON  {"type": "node_start"|"node_end"|"node_error",
#                    "node": name, "label": label, "ts": "<iso>"}
# ─────────────────────────────────────────────────────────────────────────────

_STATUS_TTL = 86400  # 24 hours

_NODE_LABELS = {
    "input_validator":         "Validating Input",
    "request_correction_node": "Requesting Correction",
    "context_node":            "Extracting Context",
    "enriched_context_node":   "Enriching Context",
    "payload_builder_node":    "Building Payload",
    "A5_detection_agent":      "Detection Agent",
    "A1_similar_cases_agent":  "Similar Cases Agent",
    "A2_pattern_agent":        "Pattern Agent",
    "A3_severity_agent":       "Severity Agent",
    "A4_occurrence_agent":     "Occurrence Agent",
    "rpn_calculator_node":     "Calculating RPN",
    "A6_regulatory_agent":     "Regulatory Agent",
    "A7_reasoning_agent":      "AI Reasoning Agent",
    "finalize_node":           "Finalizing Report",
}

_NODE_AGENT_IDS = {
    "A5_detection_agent":      "A5",
    "A1_similar_cases_agent":  "A1",
    "A2_pattern_agent":        "A2",
    "A3_severity_agent":       "A3",
    "A4_occurrence_agent":     "A4",
    "A6_regulatory_agent":     "A6",
    "A7_reasoning_agent":      "A7",
}

def write_agent_status(thread_id: str, node: str, status: str) -> None:
    ts  = datetime.datetime.now().isoformat()
    key = f"agent_status:{thread_id}"
    redis_client.hset(key, node, json.dumps({"status": status, "ts": ts}))
    redis_client.expire(key, _STATUS_TTL)


def publish_agent_event(thread_id: str, event: dict) -> None:
    channel = f"agent_events:{thread_id}"
    redis_client.publish(channel, json.dumps(event))
