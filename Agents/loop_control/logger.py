"""
Logging helpers for Loop Control agent.
"""

from datetime import datetime
from pathlib import Path

from Agents.loop_control.state import LoopControlInput


log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
LOG_FILE = log_dir / "loop_control.log"


def _log(message: str, mode: str = "a"):
	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	line = f"{timestamp} | INFO     | {message}\n"
	with open(LOG_FILE, mode, encoding="utf-8") as handle:
		handle.write(line)


def reset_log():
	_log("=" * 80, mode="w")
	_log("LOOP CONTROL RUN START")


def log_request(payload: LoopControlInput):
	reset_log()
	_log("[REQUEST]")
	_log(f"  current_loop_count={payload.current_loop_count}")
	_log(f"  max_loops={payload.max_loops}")
	_log(f"  current_cause_confidence={payload.current_cause_confidence}")
	_log(f"  why_chain_items={len(payload.full_why_chain)}")


def log_node_start(node_name: str):
	_log("-" * 80)
	_log(f"[NODE START] {node_name}")


def log_node_end(node_name: str, summary: str = ""):
	_log(f"[NODE END] {node_name}")
	if summary:
		_log(f"  {summary}")


def log_error(location: str, error: str):
	_log(f"[ERROR] {location}: {error}")

