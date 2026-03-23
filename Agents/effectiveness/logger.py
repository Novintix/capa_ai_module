"""
logger.py

Logging utility for CAPA Effectiveness Evaluation Agent.

Fixes applied:
- FIX 1: Added console (StreamHandler) alongside file logging for dev visibility
- FIX 2: log_node_entry guards against missing/short root cause string (index error)
- FIX 3: log_node_exit logs retry_count and validation_error_message for retry traceability
- FIX 4: log_evaluation logs full action detail including recurrence and confidence
- FIX 5: Added log_retry() dedicated function for retry loop visibility
- FIX 6: Added log_validation_pass() for explicit audit trail on successful validation
- FIX 7: propagate=False prevents duplicate log entries if root logger is configured
"""

import logging
from pathlib import Path


# ── Directory & file setup ──────────────────────────────────────────────────
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "effectiveness.log"

# ── Logger ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("effectiveness_agent")
logger.setLevel(logging.DEBUG)

# FIX 7: Prevent duplicate log lines when root logger also has handlers
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler — INFO and above persisted to disk
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # FIX 1: Console handler — DEBUG and above shown during development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# ── Log functions ────────────────────────────────────────────────────────────

def log_node_entry(node_name: str, state: dict) -> None:
    """Log when a node begins execution."""
    logger.info(f"[NODE START] {node_name}")

    root_cause = state.get("evaluation_input", {}).get("root_cause_description", "N/A")

    # FIX 2: Guard against short or empty root cause string before slicing
    preview = root_cause[:80] + "..." if len(root_cause) > 80 else root_cause
    logger.info(f"  Root Cause Preview : {preview}")

    action_count = len(state.get("evaluation_input", {}).get("actions", []))
    logger.info(f"  Actions in Input   : {action_count}")

    # FIX 3: Log retry context so loop iterations are fully traceable
    retry_count = state.get("retry_count", 0)
    if retry_count > 0:
        logger.warning(f"  Retry Attempt      : {retry_count}")
        logger.warning(f"  Prior Violation    : {state.get('validation_error_message', 'N/A')}")


def log_node_exit(node_name: str, state: dict) -> None:
    """Log when a node completes successfully."""
    logger.info(f"[NODE END] {node_name}")
    logger.info(f"  Evaluated Actions  : {len(state.get('evaluated_actions', []))}")
    logger.info(f"  Confidence Score   : {state.get('confidence_score', 0.0):.2f}")

    # FIX 3: Confirm error state was cleared on exit
    error = state.get("error")
    if error:
        logger.warning(f"  Error on exit      : {error}")
    else:
        logger.info(f"  Error State        : None (clean)")


def log_error(location: str, error: str) -> None:
    """Log an error with location context."""
    logger.error(f"[ERROR] in {location}")
    logger.error(f"  Detail: {error}")


def log_evaluation(evaluated_actions: list) -> None:
    """
    Log a summary of all evaluated actions after LLM scoring.
    FIX 4: Includes recurrence level and confidence for full audit traceability.
    """
    logger.info(f"[EVALUATION SUMMARY] Total Actions Scored: {len(evaluated_actions)}")
    for idx, action in enumerate(evaluated_actions, 1):
        logger.info(
            f"  {idx}. [{action.get('action_id', 'N/A')}] "
            f"Score={action.get('effectiveness_score', 'N/A'):>3} | "
            f"RC Addressed={action.get('root_cause_addressed', 'N/A'):<10} | "
            f"Recurrence={action.get('recurrence_prevention_level', 'N/A'):<7} | "
            f"Confidence={action.get('confidence_level', 'N/A'):<7} | "
            f"Impact={action.get('system_impact', 'N/A')}"
        )


def log_retry(retry_count: int, max_retries: int, violation: str) -> None:
    """
    FIX 5: Dedicated retry log — makes retry loop fully visible in log output.
    Called from graph.py should_retry() before routing back to evaluate_actions.
    """
    logger.warning(f"[RETRY {retry_count}/{max_retries}] Validation failed — routing back to evaluate_actions.")
    logger.warning(f"  Violation: {violation}")


def log_validation_pass(evaluated_actions: list) -> None:
    """
    FIX 6: Explicit audit trail entry when all guardrails pass.
    Important for GxP — a passed validation should be as visible as a failure.
    """
    logger.info(f"[VALIDATION PASSED] All {len(evaluated_actions)} actions cleared GxP guardrails.")
    for action in evaluated_actions:
        logger.info(
            f"  PASSED [{action.get('action_id')}] "
            f"Score={action.get('effectiveness_score')} | "
            f"RC={action.get('root_cause_addressed')} | "
            f"Recurrence={action.get('recurrence_prevention_level')} | "
            f"Confidence={action.get('confidence_level')}"
        )