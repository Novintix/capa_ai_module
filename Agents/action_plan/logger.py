"""
logger.py

Logging utility for CAPA Action Plan Agent.
"""

import logging
from datetime import datetime
from pathlib import Path


# Create logs directory
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "action_plan.log"

logger = logging.getLogger("action_plan_agent")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def log_node_entry(node_name: str, state: dict):
    logger.info(f"[NODE START] {node_name}")
    root_causes = state.get("capa_input", {}).get("primary_root_cause", "N/A")
    logger.info(f"  Primary Root Cause: {root_causes}")


def log_node_exit(node_name: str, state: dict):
    logger.info(f"[NODE END] {node_name}")
    logger.info(f"  Action Items Count: {state.get('total_actions', 0)}")
    logger.info(f"  Confidence Score: {state.get('confidence_score', 0)}")


def log_error(location: str, error: str):
    logger.error(f"[ERROR] {location}: {error}")


def log_action_plan(action_items: list, total: int):
    logger.info(f"[ACTION PLAN GENERATED] Total actions: {total}")
    for idx, action in enumerate(action_items, 1):
        logger.info(f"  {idx}. {action.get('action_type')} - Due: {action.get('planned_due_date')}")
