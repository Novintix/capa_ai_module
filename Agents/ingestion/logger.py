"""
Logging utility for Document Ingestion Agent
Logs all operations to Agents/logs/ingestion.log
"""

import logging
from datetime import datetime
from pathlib import Path

# Create logs directory at Agents level
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("ingestion_agent")
logger.setLevel(logging.INFO)

# File handler - ingestion.log in Agents/logs/
log_file = log_dir / "ingestion.log"
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
    logger.info(f"  Document ID: {state.get('document_id', 'N/A')}")
    logger.info(f"  Next Step: {state.get('next_step', 'N/A')}")


def log_node_exit(node_name: str, updates: dict):
    """Log when a node completes execution"""
    logger.info(f"[NODE END] {node_name}")
    for key, value in updates.items():
        if key not in ['extracted_text', 'structured_data']:  # Skip large data
            logger.info(f"  {key}: {value}")


def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
    """Log routing decisions"""
    logger.info(f"[ROUTING] {from_node} -> {to_node}")
    if reason:
        logger.info(f"  Reason: {reason}")


def log_error(location: str, error: str):
    """Log errors"""
    logger.error(f"[ERROR] {location}: {error}")


def log_api_request(endpoint: str, document_id: str, file_path: str):
    """Log API requests"""
    logger.info("="*60)
    logger.info(f"[API REQUEST] {endpoint}")
    logger.info(f"  Document ID: {document_id}")
    logger.info(f"  File Path: {file_path}")
    logger.info(f"  Timestamp: {datetime.now().isoformat()}")


def log_api_response(document_id: str, success: bool, processing_time: float):
    """Log API responses"""
    logger.info(f"[API RESPONSE] Document ID: {document_id}")
    logger.info(f"  Success: {success}")
    logger.info(f"  Processing Time: {processing_time:.2f}s")
    logger.info("="*60)


def log_extraction_start(document_type: str, extraction_mode: str):
    """Log extraction start"""
    logger.info(f"[EXTRACTION START] Type: {document_type}, Mode: {extraction_mode}")


def log_extraction_complete(text_length: int, has_structured: bool):
    """Log extraction completion"""
    logger.info(f"[EXTRACTION COMPLETE] Text length: {text_length}, Structured: {has_structured}")