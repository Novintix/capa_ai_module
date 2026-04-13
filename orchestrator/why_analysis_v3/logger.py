"""
Logger for Why Analysis V3 orchestrator.
"""

import logging
import os
from datetime import datetime

LOG_DIR = "Agents/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("why_analysis_v3")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(os.path.join(LOG_DIR, "why_analysis_v3.log"), encoding='utf-8')
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_node_entry(node: str, state: dict):
    """Log entry into a node."""
    loop = state.get("current_loop_count", 0)
    session = state.get("session_id", "unknown")
    logger.info(f"[{session}] [Loop {loop}] -> Entering node: {node}")


def log_node_exit(node: str, updates: dict):
    """Log exit from a node."""
    next_step = updates.get("next_step", "END")
    logger.info(f"-> Exiting node: {node} | Next: {next_step}")


def log_routing_decision(from_node: str, to_node: str, reason: str):
    """Log routing decision."""
    logger.info(f"[ROUTING] {from_node} → {to_node} | Reason: {reason}")


def log_iteration(loop: int, question: str, selected_cause: str, confidence: float):
    """Log iteration summary."""
    logger.info(
        f"[ITERATION {loop}] Question: {question[:80]}... | "
        f"Selected: {selected_cause[:80]}... | Confidence: {confidence:.2f}"
    )


def log_error(location: str, message: str):
    """Log error."""
    logger.error(f"[ERROR] {location}: {message}")


def log_api_request(endpoint: str, complaint_id: str):
    """Log API request."""
    logger.info(f"[API REQUEST] {endpoint} | complaint_id: {complaint_id}")


def log_api_response(complaint_id: str, status: str, stopping_reason: str):
    """Log API response."""
    logger.info(
        f"[API RESPONSE] complaint_id: {complaint_id} | "
        f"status: {status} | stopping_reason: {stopping_reason}"
    )
