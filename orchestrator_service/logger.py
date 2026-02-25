import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Orchestrator")


def _thread_prefix(state: dict = None, thread_id: str = None) -> str:
    """Extract a short thread label for log context."""
    if thread_id:
        return f"[{thread_id[:8]}...]"
    if state:
        cid = state.get("complaint_id", "?")
        return f"[{cid}]"
    return "[GLOBAL]"


def log_node_entry(node_name: str, state: dict, thread_id: str = None):
    prefix = _thread_prefix(state, thread_id)
    logger.info(f"{prefix} ──▶ ENTER {node_name}")
    logger.debug(f"{prefix}     state={json.dumps(state, default=str)}")


def log_node_exit(node_name: str, update: dict, thread_id: str = None):
    prefix = _thread_prefix(thread_id=thread_id)
    logger.info(f"{prefix} ◀── EXIT  {node_name} | update_keys={list(update.keys())}")


def log_error(node_name: str, error: Exception, thread_id: str = None):
    prefix = _thread_prefix(thread_id=thread_id)
    logger.error(f"{prefix} ✖  ERROR  {node_name} | {type(error).__name__}: {error}")

