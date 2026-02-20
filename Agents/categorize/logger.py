import logging
import os
from datetime import datetime

LOG_DIR = "Agents/logs"
LOG_FILE = os.path.join(LOG_DIR, "categorize.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("categorize_agent")
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

def log_prompt(prompt: str):
    logger.info(f"[PROMPT]\n{prompt}\n")

def log_raw_response(response: str, run_number: int):
    logger.info(f"[RAW RESPONSE - Attempt {run_number}]\n{response}\n")

def log_error(location: str, error: str):
    logger.error(f"[ERROR in {location}] {error}")

def log_request(question: str, num_causes: int):
    logger.info(f"[REQUEST] Question: {question} | Causes: {num_causes}")

def log_final_output(summary: dict):
    logger.info(f"[FINAL OUTPUT] Summary: {summary}")
