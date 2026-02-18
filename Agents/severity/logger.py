"""
logger.py

Central logging utility for Severity Agent.

Features:
- File logging (logs/process.log)
- Console logging (terminal visibility)
- Node lifecycle tracking
- API request/response logging
- Error logging
- Prevents duplicate handlers during FastAPI reload
"""


import logging
from datetime import datetime
from pathlib import Path


# --------------------------------------------------
# Create logs directory at project root
# --------------------------------------------------

log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "process.log"


# --------------------------------------------------
# Configure Logger
# --------------------------------------------------

logger = logging.getLogger("severity_agent")
logger.setLevel(logging.INFO)

# Prevent duplicate handlers (important in FastAPI reload)
if not logger.handlers:

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# --------------------------------------------------
# Node Logging
# --------------------------------------------------

def log_node_entry(node_name: str, state: dict):
    """Log when a node starts execution"""
    logger.info(f"[NODE START] {node_name}")
    logger.info(f"  Issue: {state.get('issue', 'N/A')}")


def log_node_exit(node_name: str, updates: dict):
    """Log when a node completes execution"""
    logger.info(f"[NODE END] {node_name}")

    for key, value in updates.items():
        if key != "issue":  # Skip large text logging
            logger.info(f"  {key}: {value}")


# --------------------------------------------------
# Routing Logging
# --------------------------------------------------

def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
    logger.info(f"[ROUTING] {from_node} -> {to_node}")
    if reason:
        logger.info(f"  Reason: {reason}")


# --------------------------------------------------
# Error Logging
# --------------------------------------------------

def log_error(location: str, error: str):
    logger.error(f"[ERROR] {location}: {error}")


# --------------------------------------------------
# API Logging
# --------------------------------------------------

def log_api_request(endpoint: str, issue: str):
    logger.info("=" * 60)
    logger.info(f"[API REQUEST] {endpoint}")
    logger.info(f"  Issue: {issue[:150]}...")  # Truncate long text
    logger.info(f"  Timestamp: {datetime.now().isoformat()}")


def log_api_response(severity_score: int, severity_label: str):
    logger.info(f"[API RESPONSE]")
    logger.info(f"  Severity Score: {severity_score}")
    logger.info(f"  Severity Label: {severity_label}")
    logger.info("=" * 60)
