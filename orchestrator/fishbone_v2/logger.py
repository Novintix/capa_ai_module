"""
Fishbone v2 Orchestrator Logger
Structured logging for all orchestrator operations
"""

import logging
import os
from typing import Optional, Dict, Any

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

# Configure logger
logger = logging.getLogger("fishbone_v2_orchestrator")
logger.setLevel(logging.INFO)

# File handler with UTF-8 encoding
log_file = os.path.join(log_dir, "fishbone_v2.log")
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def log_orchestrator_start(complaint_id: str, mode: str, max_depth: int):
    """Log orchestrator start"""
    logger.info(f"[ORCHESTRATOR START] complaint_id={complaint_id}, mode={mode}, max_depth={max_depth}")


def log_orchestrator_complete(complaint_id: str, depth: int, has_root_cause: bool, execution_time: float):
    """Log orchestrator completion"""
    logger.info(
        f"[ORCHESTRATOR COMPLETE] complaint_id={complaint_id}, depth={depth}, "
        f"has_root_cause={has_root_cause}, execution_time={execution_time:.2f}s"
    )


def log_state_transition(complaint_id: str, from_state: str, to_state: str, reason: str):
    """Log state transition"""
    logger.info(f"[STATE TRANSITION] complaint_id={complaint_id}, {from_state} → {to_state}, reason={reason}")


def log_iteration(depth: int, causes_found: int, selected_cause: Optional[str]):
    """Log iteration completion"""
    logger.info(
        f"[ITERATION] depth={depth}, causes_found={causes_found}, "
        f"selected_cause={selected_cause[:50] if selected_cause else 'None'}"
    )


def log_agent_call(agent_name: str, input_data: dict, success: Optional[bool], error: Optional[str] = None):
    """Log agent call"""
    status = "SUCCESS" if success else "ERROR" if success is False else "CALLED"
    msg = f"[AGENT CALL] {agent_name} - {status}"
    if error:
        msg += f" - {error}"
    logger.info(msg)


def log_routing_decision(from_node: str, to_node: str, reason: str):
    """Log routing decision"""
    logger.info(f"[ROUTING] {from_node} → {to_node}, reason={reason}")


def log_memory_update(component: str, complaint_id: str, operation: str, details: str):
    """Log memory update"""
    logger.info(f"[MEMORY] {component} - complaint_id={complaint_id}, op={operation}, details={details}")


def log_error(operation: str, error_message: str):
    """Log error"""
    logger.error(f"[ERROR] {operation} - {error_message}")


def log_api_request(endpoint: str, complaint_id: str, has_fmea: bool = False):
    """Log API request"""
    logger.info(f"[API REQUEST] {endpoint}, complaint_id={complaint_id}, has_fmea={has_fmea}")


def log_api_response(complaint_id: str, root_cause_id: Optional[str], depth: int, mode: str):
    """Log API response"""
    logger.info(
        f"[API RESPONSE] complaint_id={complaint_id}, root_cause_id={root_cause_id}, "
        f"depth={depth}, mode={mode}"
    )
