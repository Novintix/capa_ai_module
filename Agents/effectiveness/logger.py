"""
logger.py

Logging utility for CAPA Effectiveness Evaluation Agent.
"""

import logging
from pathlib import Path

# Create logs directory
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "effectiveness.log"

logger = logging.getLogger("effectiveness_agent")
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
    root_cause = state.get("evaluation_input", {}).get("root_cause_description", "N/A")
    logger.info(f"  Root Cause: {root_cause[:50]}...")

def log_node_exit(node_name: str, state: dict):
    logger.info(f"[NODE END] {node_name}")
    logger.info(f"  Evaluated Actions Count: {len(state.get('evaluated_actions', []))}")
    logger.info(f"  Confidence Score: {state.get('confidence_score', 0)}")

def log_error(location: str, error: str):
    logger.error(f"[ERROR] {location}: {error}")

def log_evaluation(evaluated_actions: list):
    logger.info(f"[EVALUATION COMPLETED]")
    for idx, action in enumerate(evaluated_actions, 1):
        logger.info(f"  {idx}. Action: {action.get('action_id')} - Score: {action.get('effectiveness_score')} - Addressed: {action.get('root_cause_addressed')}")
