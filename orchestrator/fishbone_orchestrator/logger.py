"""
RCA v2 Orchestrator Logger
Logging for state machine implementation with enhanced tracking
"""

import logging
import os
from datetime import datetime
from typing import Optional


# Create logs directory if it doesn't exist
log_dir = "Agents/logs"
os.makedirs(log_dir, exist_ok=True)

# Configure logger for RCA v2
logger = logging.getLogger("rca_v2_orchestrator")
logger.setLevel(logging.INFO)

# Create file handler with UTF-8 encoding to handle Unicode characters
log_file = os.path.join(log_dir, "rca_v2.log")
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


def _sanitize_text(text: str) -> str:
    """Remove problematic Unicode characters for logging"""
    if not text:
        return text
    # Replace arrow and special spaces with ASCII equivalents
    return (text
            .replace('→', '->')
            .replace('\u202f', ' ')  # Narrow no-break space
            .replace('\u2009', ' ')  # Thin space
            .replace('±', '+/-'))


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
    # Sanitize question and selected cause text
    safe_question = _sanitize_text(question)
    safe_selected = _sanitize_text(selected_cause) if selected_cause else 'None'
    
    logger.info(
        f"Iteration {depth} - Question: '{safe_question}', "
        f"Causes Found: {causes_found}, "
        f"Selected: {safe_selected}"
    )


def log_error(operation: str, error_message: str):
    """Log error details"""
    safe_error = _sanitize_text(error_message)
    logger.error(f"Error in {operation}: {safe_error}")


def log_agent_call(agent_name: str, input_data: dict, success: bool, error: Optional[str] = None):
    """Log sub-agent calls"""
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"Agent Call - {agent_name}: {status}, "
        f"Input: {input_data.get('question_id', 'N/A')}"
    )
    if error:
        safe_error = _sanitize_text(error)
        logger.error(f"Agent Call Error - {agent_name}: {safe_error}")


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


def log_state_transition(complaint_id: str, from_state: str, to_state: str, reason: str):
    """Log state machine transition"""
    safe_reason = _sanitize_text(reason)
    logger.info(
        f"State Transition - Complaint: {complaint_id}, "
        f"{from_state} -> {to_state}, "
        f"Reason: {safe_reason}"
    )


def log_memory_update(complaint_id: str, memory_type: str, action: str, details: str = ""):
    """Log memory updates"""
    safe_details = _sanitize_text(details)
    logger.info(
        f"Memory Update - Complaint: {complaint_id}, "
        f"Type: {memory_type}, "
        f"Action: {action}, "
        f"Details: {safe_details}"
    )


def log_llm_context(complaint_id: str, context_type: str, context_size: int):
    """Log LLM context creation"""
    logger.info(
        f"LLM Context - Complaint: {complaint_id}, "
        f"Type: {context_type}, "
        f"Size: {context_size} chars"
    )


def log_routing_decision(source: str, destination: str, reason: str):
    """Log routing decision between agents"""
    safe_reason = _sanitize_text(reason)
    logger.info(f"Routing Decision - {source} -> {destination}: {safe_reason}")