import logging
import os
from datetime import datetime

LOG_DIR = "Agents/logs"
LOG_FILE = os.path.join(LOG_DIR, "similar_cases.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("similar_cases_agent")
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


def log_embedding(query: str, embedding_dim: int):
    logger.info(f"[EMBEDDING] Query: '{query[:80]}...' | Dimension: {embedding_dim}")


def log_vector_search(limit: int, threshold: float, results_count: int):
    logger.info(f"[VECTOR SEARCH] Limit: {limit} | Threshold: {threshold} | Results: {results_count}")


def log_error(location: str, error: str):
    logger.error(f"[ERROR in {location}] {error}")


def log_request(query: str):
    logger.info(f"[REQUEST] Query: {query[:100]}...")


def log_final_output(similar_count: int, threshold: float):
    logger.info(f"[FINAL OUTPUT] Similar Cases: {similar_count} | Threshold: {threshold}")


def log_api_request(endpoint: str, query: str):
    logger.info(f"[API REQUEST] {endpoint} | Query: {query[:80]}...")


def log_api_response(similar_count: int):
    logger.info(f"[API RESPONSE] Similar Cases Found: {similar_count}")
