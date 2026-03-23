"""
Logging utility for Validation Agent
Logs all operations to Agents/logs/validation.log
"""

import logging
from datetime import datetime
from pathlib import Path

# Create logs directory at Agents level
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("validation_agent")
logger.setLevel(logging.INFO)

if not logger.handlers:
	log_file = log_dir / "validation.log"
	file_handler = logging.FileHandler(log_file, encoding="utf-8")
	file_handler.setLevel(logging.INFO)

	formatter = logging.Formatter(
		"%(asctime)s - %(name)s - %(levelname)s - %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S",
	)
	file_handler.setFormatter(formatter)
	logger.addHandler(file_handler)


def log_node_entry(node_name: str, state: dict):
	logger.info(f"[NODE START] {node_name}")
	logger.info(f"  Complaint ID: {state.get('complaint_id', 'N/A')}")
	logger.info(f"  Next Step: {state.get('next_step', 'N/A')}")


def log_node_exit(node_name: str, updates: dict):
	logger.info(f"[NODE END] {node_name}")
	for key, value in updates.items():
		if key not in ["evidence_records", "cause_validation_results", "validated_causes"]:
			logger.info(f"  {key}: {value}")


def log_routing_decision(from_node: str, to_node: str, reason: str = ""):
	logger.info(f"[ROUTING] {from_node} -> {to_node}")
	if reason:
		logger.info(f"  Reason: {reason}")


def log_error(location: str, error: str):
	logger.error(f"[ERROR] {location}: {error}")


def log_api_request(endpoint: str, complaint_id: str, cause_count: int):
	logger.info("=" * 60)
	logger.info(f"[API REQUEST] {endpoint}")
	logger.info(f"  Complaint ID: {complaint_id}")
	logger.info(f"  Cause Count: {cause_count}")
	logger.info(f"  Timestamp: {datetime.now().isoformat()}")


def log_api_response(complaint_id: str, validated_causes: int, confidence: float):
	logger.info(f"[API RESPONSE] Complaint ID: {complaint_id}")
	logger.info(f"  Validated Causes: {validated_causes}")
	logger.info(f"  Overall Confidence: {confidence}")
	logger.info("=" * 60)


def log_validation_summary(total_causes: int, validated_causes: int, confidence: float):
	logger.info("[VALIDATION SUMMARY]")
	logger.info(f"  Total Input Causes: {total_causes}")
	logger.info(f"  Validated Causes: {validated_causes}")
	logger.info(f"  Overall Confidence: {confidence}")
