import logging
from pathlib import Path

log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / "aireasoning.log"

logger = logging.getLogger("aireasoning")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(log_file, mode='a')
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def reset_log():
    """Clear the log file at the start of each new API request."""
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)
    # Truncate file
    open(log_file, 'w').close()
    # Re-attach handler in append mode
    handler = logging.FileHandler(log_file, mode='a')
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_node_start(node_name: str):
    logger.info(f"[NODE START] {node_name}")


def log_node_end(node_name: str, message: str = ""):
    logger.info(f"[NODE END] {node_name} | {message}")


def log_prompt(prompt: str):
    logger.info(f"[PROMPT]\n{prompt}")


def log_raw_response(response: str):
    logger.info(f"[RAW RESPONSE]\n{response}")


def log_error(location: str, error: str):
    logger.error(f"[ERROR] {location} | {error}")


def log_request(complaint_id: str, risk_score: int):
    logger.info(f"[REQUEST] complaint_id={complaint_id} | risk_score={risk_score}")


def log_final_output(complaint_id: str, confidence: str):
    logger.info(f"[FINAL OUTPUT] complaint_id={complaint_id} | confidence={confidence}")


def log_output(output: dict):
    import json
    logger.info(f"[OUTPUT]\n{json.dumps(output, indent=2)}")


def log_output_audit(output: dict):
    """Cross-check output fields — flags missing or empty values for observability."""
    logger.info("[OUTPUT AUDIT] Validating AI Reasoning response fields:")
    expected_fields = ["reasoning", "key_factors", "recommendations", "confidence_level"]
    for field in expected_fields:
        value = output.get(field)
        if value is None:
            logger.warning(f"  [{field}] MISSING — field not returned by LLM")
        elif isinstance(value, list) and len(value) == 0:
            logger.warning(f"  [{field}] EMPTY LIST — no items returned")
        elif isinstance(value, str) and not value.strip():
            logger.warning(f"  [{field}] EMPTY STRING — no content returned")
        else:
            summary = f"{len(value)} items" if isinstance(value, list) else f"\"{value[:80]}...\"" if isinstance(value, str) and len(value) > 80 else f"\"{value}\""
            logger.info(f"  [{field}] OK — {summary}")

