"""
Regulatory Agent Logger
Centralized logging for the Regulatory Agent.
"""

import logging
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("RegulatoryAgent")
logger.setLevel(logging.INFO)

# File handler only 
log_file = log_dir / f"regulatory_agent_{datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

# Add handler
logger.addHandler(file_handler)


def log_api_request(endpoint: str, complaint_id: str, has_policy: bool):
    """Log API request"""
    logger.info(f"API Request - Endpoint: {endpoint}, Complaint: {complaint_id}, Has Policy: {has_policy}")


def log_api_response(complaint_id: str, reportable: bool, matched_rule_id: str):
    """Log API response"""
    logger.info(f"API Response - Complaint: {complaint_id}, Reportable: {reportable}, Rule: {matched_rule_id}")


def log_node_entry(node_name: str, state: dict):
    """Log node entry"""
    complaint_id = state.get("complaint_id", "unknown")
    logger.info(f"Node Entry - {node_name} - Complaint: {complaint_id}")


def log_node_exit(node_name: str, updates: dict):
    """Log node exit"""
    next_step = updates.get("next_step", "unknown")
    logger.info(f"Node Exit - {node_name} - Next: {next_step}")


def log_routing_decision(from_node: str, to_node: str, reason: str):
    """Log routing decision"""
    logger.info(f"Routing - {from_node} -> {to_node} - Reason: {reason}")


def log_error(node_name: str, error_message: str):
    """Log error"""
    logger.error(f"Error in {node_name}: {error_message}")


def log_rule_match(rule_id: str, complaint_id: str):
    """Log rule match"""
    logger.info(f"Rule Match - Rule: {rule_id}, Complaint: {complaint_id}")


def log_no_rule_match(complaint_id: str):
    """Log no rule match"""
    logger.info(f"No Rule Match - Complaint: {complaint_id}")
