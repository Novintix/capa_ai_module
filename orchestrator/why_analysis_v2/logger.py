"""
Logger for Why Analysis V2 orchestrator.
"""

import logging
import os
from typing import Any, Dict, Optional


log_dir = "Agents/logs"
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger("why_analysis_v2")
logger.setLevel(logging.INFO)

log_file = os.path.join(log_dir, "why_analysis_v2.log")
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)


def log_orchestrator_start(complaint_id: str, mode: str, max_loops: int) -> None:
    logger.info(
        "Orchestrator Started - complaint_id=%s mode=%s max_loops=%s",
        complaint_id,
        mode,
        max_loops,
    )


def log_orchestrator_complete(complaint_id: str, status: str, depth: int, execution_time: float) -> None:
    logger.info(
        "Orchestrator Complete - complaint_id=%s status=%s depth=%s execution_time=%.2fs",
        complaint_id,
        status,
        depth,
        execution_time,
    )


def log_api_request(endpoint: str, complaint_id: str) -> None:
    logger.info("API Request - endpoint=%s complaint_id=%s", endpoint, complaint_id)


def log_api_response(complaint_id: str, status: str, stopping_reason: Optional[str]) -> None:
    logger.info(
        "API Response - complaint_id=%s status=%s stopping_reason=%s",
        complaint_id,
        status,
        stopping_reason,
    )


def log_node_entry(node_name: str, state: Dict[str, Any]) -> None:
    logger.info(
        "Node Entry - node=%s complaint_id=%s loop=%s",
        node_name,
        state.get("complaint_id"),
        state.get("current_loop_count"),
    )


def log_node_exit(node_name: str, updates: Dict[str, Any]) -> None:
    logger.info("Node Exit - node=%s next_step=%s", node_name, updates.get("next_step"))


def log_iteration(loop: int, question: str, selected_cause: str, confidence: float) -> None:
    logger.info(
        "Iteration - loop=%s question=%s selected_cause=%s confidence=%.3f",
        loop,
        question,
        selected_cause,
        confidence,
    )


def log_routing_decision(node_name: str, next_step: str, reason: str) -> None:
    logger.info("Routing - node=%s next=%s reason=%s", node_name, next_step, reason)


def log_error(operation: str, message: str) -> None:
    logger.error("Error - operation=%s message=%s", operation, message)
