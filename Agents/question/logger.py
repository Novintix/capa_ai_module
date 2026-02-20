"""
Logging utility for Why Question Agent.
Logs all operations to the central Agents/logs/question.log file.
"""

import logging
from pathlib import Path


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Central log directory: Agents/logs/question.log
central_log_dir = Path(__file__).parent.parent / "logs"
central_log_dir.mkdir(exist_ok=True)

logger = logging.getLogger("why_question_agent")
logger.setLevel(logging.INFO)

# Prevent duplicate handlers when module is reloaded
if not logger.handlers:
    file_handler = logging.FileHandler(central_log_dir / "question.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def log_node_entry(node_name: str, state: dict):
    """Log when a node starts execution."""
    logger.info(f"[NODE START] {node_name}")
    logger.info(f"  Complaint ID : {state.get('complaint_id') or 'N/A'}")
    logger.info(f"  Iteration    : {state.get('iteration', 0)}")
    logger.info(f"  Next Step    : {state.get('next_step') or 'not set'}")
    logger.info(f"  Why Depth    : {state.get('why_depth') or 'not set yet'}")


def log_node_exit(node_name: str, updates: dict):
    """Log when a node completes execution."""
    logger.info(f"[NODE END] {node_name}")
    for key, value in updates.items():
        # Skip large input fields
        if key in ("complaint", "evidence", "sop"):
            logger.info(f"  {key}: <present, {len(str(value))} chars>")
        else:
            logger.info(f"  {key}: {value}")


def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
    """Log routing decisions between nodes."""
    logger.info(f"[ROUTING] {from_node} -> {to_node}")
    if reason:
        logger.info(f"  Reason: {reason}")


def log_error(location: str, error: str):
    """Log errors."""
    logger.error(f"[ERROR] {location}: {error}")


def log_api_request(endpoint: str, complaint_id: str, why_depth: int = None):
    """Log incoming API requests."""
    logger.info(f"[API REQUEST] {endpoint}")
    logger.info(f"  Complaint ID : {complaint_id}")
    if why_depth is not None:
        logger.info(f"  Why Depth    : {why_depth}")


def log_api_response(endpoint: str, complaint_id: str, why_depth: int, success: bool):
    """Log outgoing API responses."""
    status = "SUCCESS" if success else "FAILURE"
    logger.info(f"[API RESPONSE] {endpoint} — {status}")
    logger.info(f"  Complaint ID : {complaint_id}")
    logger.info(f"  Why depth    : {why_depth}")
