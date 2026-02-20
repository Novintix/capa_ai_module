"""
Logging utility for Cause Generation Agent
Logs all operations to Agents/logs/cause_generation.log
"""

import logging
from datetime import datetime
from pathlib import Path

# Create logs directory at Agents level
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("cause_generation_agent")
logger.setLevel(logging.INFO)

# File handler - cause_generation.log in Agents/logs/
log_file = log_dir / "cause_generation.log"
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
    logger.info(f"  Question ID: {state.get('question_id', 'N/A')}")
    logger.info(f"  Next Step: {state.get('next_step', 'N/A')}")


def log_node_exit(node_name: str, updates: dict):
    """Log when a node completes execution"""
    logger.info(f"[NODE END] {node_name}")
    for key, value in updates.items():
        if key not in ['fmea_data', 'matched_rows', 'extracted_causes']:  # Skip large data
            logger.info(f"  {key}: {value}")


def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
    """Log routing decisions"""
    logger.info(f"[ROUTING] {from_node} -> {to_node}")
    if reason:
        logger.info(f"  Reason: {reason}")


def log_error(location: str, error: str):
    """Log errors"""
    logger.error(f"[ERROR] {location}: {error}")


def log_api_request(endpoint: str, question_id: str, has_fmea: bool):
    """Log API requests"""
    logger.info("="*60)
    logger.info(f"[API REQUEST] {endpoint}")
    logger.info(f"  Question ID: {question_id}")
    logger.info(f"  Has FMEA: {has_fmea}")
    logger.info(f"  Timestamp: {datetime.now().isoformat()}")


def log_api_response(question_id: str, causes_found: int):
    """Log API responses"""
    logger.info(f"[API RESPONSE] Question ID: {question_id}")
    logger.info(f"  Causes Found: {causes_found}")
    logger.info("="*60)


def log_fmea_parsing(rows_parsed: int):
    """Log FMEA parsing"""
    logger.info(f"[FMEA PARSING] Rows parsed: {rows_parsed}")


def log_matching(matched_count: int):
    """Log matching results"""
    logger.info(f"[MATCHING] Matched rows: {matched_count}")
