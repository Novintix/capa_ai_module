"""
Logger utilities for Root Cause Analysis coordinator.
"""

import logging
from typing import Optional


logger = logging.getLogger("root_cause_analysis")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [RCA] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_info(message: str) -> None:
    logger.info(message)


def log_error(operation: str, error: str, complaint_id: Optional[str] = None) -> None:
    prefix = f"complaint_id={complaint_id} " if complaint_id else ""
    logger.error("%soperation=%s error=%s", prefix, operation, error)


def log_transition(complaint_id: str, from_phase: str, to_phase: str, reason: str) -> None:
    logger.info(
        "complaint_id=%s transition %s -> %s reason=%s",
        complaint_id,
        from_phase,
        to_phase,
        reason,
    )
