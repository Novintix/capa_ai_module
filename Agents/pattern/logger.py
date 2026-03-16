import logging
import os
from datetime import datetime
from pathlib import Path

# Create logs directory at Agents level
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("pattern_agent")
logger.setLevel(logging.INFO)

# log file - pattern.log in Agents/logs/
log_file = log_dir / "pattern.log"

# Prevent duplicate handlers
if not logger.handlers:
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
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
        if key != 'historical_complaints':  # Skip large data
            logger.info(f"  {key}: {value}")

def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
    """Log routing decisions"""
    logger.info(f"[ROUTING] {from_node} -> {to_node}")
    if reason:
        logger.info(f"  Reason: {reason}")

def log_error(location: str, error: str):
    """Log errors"""
    logger.error(f"[ERROR] {location}: {error}")

def log_api_request(endpoint: str, complaint_id: str):
    """Log API requests"""
    logger.info("="*60)
    logger.info(f"[API REQUEST] {endpoint}")
    logger.info(f"  Complaint ID: {complaint_id}")
    logger.info(f"  Timestamp: {datetime.now().isoformat()}")

def log_api_response(complaint_id: str, trend_score: int):
    """Log API responses"""
    logger.info(f"[API RESPONSE] Complaint ID: {complaint_id}")
    logger.info(f"  Trend Score: {trend_score}")
    logger.info("="*60)
