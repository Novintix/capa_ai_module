"""
Logging utility for Detection Agent
Logs all operations to logs/process.log
"""

import logging
from datetime import datetime
from pathlib import Path

# Create logs directory in agent root (parent of detection)
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("detection_agent")
logger.setLevel(logging.INFO)

# File handler
log_file = log_dir / "process.log"
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

# Add handler
logger.addHandler(file_handler)


def log_node_entry(node_name: str, state: dict):
    """Log when a node starts execution"""
    logger.info(f"[NODE START] {node_name}")
    logger.info(f"  Iteration: {state.get('iteration', 0)}")
    logger.info(f"  Next Step: {state.get('next_step', 'N/A')}")


def log_node_exit(node_name: str, updates: dict):
    """Log when a node completes execution"""
    logger.info(f"[NODE END] {node_name}")
    for key, value in updates.items():
        if key not in ['policy_text', 'policy_rules']:  # Skip large data
            logger.info(f"  {key}: {value}")


def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
    """Log routing decisions"""
    logger.info(f"[ROUTING] {from_node} -> {to_node}")
    if reason:
        logger.info(f"  Reason: {reason}")


def log_error(location: str, error: str):
    """Log errors"""
    logger.error(f"[ERROR] {location}: {error}")


def log_api_request(endpoint: str, complaint_id: str, has_policy: bool):
    """Log API requests"""
    logger.info("="*60)
    logger.info(f"[API REQUEST] {endpoint}")
    logger.info(f"  Complaint ID: {complaint_id}")
    logger.info(f"  Has Policy: {has_policy}")
    logger.info(f"  Timestamp: {datetime.now().isoformat()}")


def log_api_response(complaint_id: str, score: int, source: str):
    """Log API responses"""
    logger.info(f"[API RESPONSE] Complaint ID: {complaint_id}")
    logger.info(f"  Detection Score: {score}")
    logger.info(f"  Decision Source: {source}")
    logger.info("="*60)
