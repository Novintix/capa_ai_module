import logging
import os
from datetime import datetime

LOG_DIR = "Agents/logs"
LOG_FILE = os.path.join(LOG_DIR, "ranking.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("ranking_agent")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def clear_logs():
    """Clear log file at start of new run."""
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== NEW RUN: {datetime.now().isoformat()} ===\n\n")


def log_node_start(node_name: str):
    logger.info(f"[NODE START] {node_name}")


def log_node_end(node_name: str, message: str = ""):
    logger.info(f"[NODE END] {node_name} | {message}")


def log_rpn_calculation(cause_id: str, rpn: int):
    logger.info(f"[RPN CALC] {cause_id} | RPN: {rpn}")


def log_normalization(max_rpn: int, count: int):
    logger.info(f"[NORMALIZE] Max RPN: {max_rpn} | Causes: {count}")


def log_evidence_eval(cause_id: str, score: float):
    logger.info(f"[EVIDENCE] {cause_id} | Score: {score:.2f}")


def log_mechanism_eval(cause_id: str, score: float):
    logger.info(f"[MECHANISM] {cause_id} | Score: {score:.2f}")


def log_proximity_eval(cause_id: str, score: float):
    logger.info(f"[PROXIMITY] {cause_id} | Score: {score:.2f}")


def log_rcps_calculation(cause_id: str, rcps: float):
    logger.info(f"[RCPS] {cause_id} | RCPS: {rcps:.4f}")


def log_final_ranking(total: int, top_cause: str):
    logger.info(f"[FINAL RANK] Total: {total} | Top Cause: {top_cause}")


def log_error(location: str, error: str):
    logger.error(f"[ERROR in {location}] {error}")


def log_api_request(endpoint: str, causes_count: int):
    logger.info(f"[API REQUEST] {endpoint} | Causes: {causes_count}")


def log_api_response(ranked_count: int, top_cause: str):
    logger.info(f"[API RESPONSE] Ranked: {ranked_count} | Top: {top_cause}")
