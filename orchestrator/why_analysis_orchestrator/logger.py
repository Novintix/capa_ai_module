"""
Logger for Why Analysis Orchestrator
Handles all logging operations for the orchestrator agent
"""

import logging
import os
from datetime import datetime
from typing import Optional


# Create logs directory if it doesn't exist
log_dir = "Agents/logs"
os.makedirs(log_dir, exist_ok=True)

# Configure logger
logger = logging.getLogger("why_analysis_orchestrator")
logger.setLevel(logging.INFO)

# Create file handler with UTF-8 encoding
log_file = os.path.join(log_dir, "why_analysis_orchestrator.log")
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)

# Add handler to logger
if not logger.handlers:
    logger.addHandler(file_handler)


def log_api_request(endpoint: str, complaint_id: str, has_fmea: bool = False):
    """Log API request details"""
    logger.info(
        f"API Request - Endpoint: {endpoint}, "
        f"Complaint ID: {complaint_id}, "
        f"Has FMEA: {has_fmea}"
    )


def log_api_response(complaint_id: str, root_cause_id: Optional[str], depth: int, mode: str):
    """Log API response details"""
    logger.info(
        f"API Response - Complaint ID: {complaint_id}, "
        f"Root Cause ID: {root_cause_id}, "
        f"Analysis Depth: {depth}, "
        f"Mode: {mode}"
    )


def log_iteration(depth: int, question: str, causes_found: int, selected_cause: Optional[str]):
    """Log details of a single Why iteration"""
    logger.info(
        f"Iteration {depth} - Question: '{question}', "
        f"Causes Found: {causes_found}, "
        f"Selected: {selected_cause or 'None'}"
    )


def log_error(operation: str, error_message: str):
    """Log error details"""
    logger.error(f"Error in {operation}: {error_message}")


def log_agent_call(agent_name: str, input_data: dict, success: bool, error: Optional[str] = None):
    """Log sub-agent calls"""
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"Agent Call - {agent_name}: {status}, "
        f"Input: {input_data.get('question_id', 'N/A')}"
    )
    if error:
        logger.error(f"Agent Call Error - {agent_name}: {error}")


def log_orchestrator_start(complaint_id: str, mode: str, max_depth: int):
    """Log orchestrator initialization"""
    logger.info(
        f"Orchestrator Started - Complaint ID: {complaint_id}, "
        f"Mode: {mode}, "
        f"Max Depth: {max_depth}"
    )


def log_orchestrator_complete(complaint_id: str, depth: int, root_cause_found: bool, execution_time: float):
    """Log orchestrator completion"""
    logger.info(
        f"Orchestrator Complete - Complaint ID: {complaint_id}, "
        f"Final Depth: {depth}, "
        f"Root Cause Found: {root_cause_found}, "
        f"Execution Time: {execution_time:.2f}s"
    )