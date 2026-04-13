"""
Fishbone v3 Orchestrator Logger
Structured logging for all V3 orchestrator operations
"""

import logging
import os
from typing import Optional, Dict, Any

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

# Configure logger
logger = logging.getLogger("fishbone_v3_orchestrator")
logger.setLevel(logging.INFO)

# File handler with UTF-8 encoding
log_file = os.path.join(log_dir, "fishbone_v3.log")
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


def log_orchestrator_start(complaint_id: str, mode: str):
    """Log orchestrator start"""
    logger.info(f"[ORCHESTRATOR START] complaint_id={complaint_id}, mode={mode}")


def log_orchestrator_complete(complaint_id: str, status: str, execution_time: float):
    """Log orchestrator completion"""
    logger.info(
        f"[ORCHESTRATOR COMPLETE] complaint_id={complaint_id}, status={status}, "
        f"execution_time={execution_time:.2f}s"
    )


def log_state_transition(complaint_id: str, from_state: str, to_state: str, reason: str):
    """Log state transition"""
    logger.info(f"[STATE TRANSITION] complaint_id={complaint_id}, {from_state} → {to_state}, reason={reason}")


def log_agent_call(agent_name: str, input_data: dict, success: Optional[bool], error: Optional[str] = None):
    """Log agent call"""
    status = "SUCCESS" if success else "ERROR" if success is False else "CALLED"
    msg = f"[AGENT CALL] {agent_name} - {status}"
    if error:
        msg += f" - {error}"
    logger.info(msg)


def log_memory_update(component: str, complaint_id: str, operation: str, details: str):
    """Log memory update"""
    logger.info(f"[MEMORY] {component} - complaint_id={complaint_id}, op={operation}, details={details}")


def log_error(operation: str, error_message: str):
    """Log error"""
    logger.error(f"[ERROR] {operation} - {error_message}")


def log_hitl_action(complaint_id: str, causes_count: int, decisions_count: int):
    """Log HITL decisions being recorded"""
    logger.info(f"[HITL ACTION] complaint_id={complaint_id}, causes={causes_count}, decisions_submitted={decisions_count}")
