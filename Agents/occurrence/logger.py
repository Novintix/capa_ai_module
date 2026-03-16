"""
logger.py

Deep Audit Logger for the Occurrence Agent.

Logs every step in detail to help detect LLM hallucinations.
Refactored to OVERWRITE the log file on every new API request (Step 1),
so the log always reflects only the latest run.

Log file: Agents/logs/occurrence.log
"""

import logging
from datetime import datetime
from pathlib import Path
from Agents.occurrence.utils import load_metrics

# -------------------------------------------------------
# Setup
# -------------------------------------------------------
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
LOG_FILE = log_dir / "occurrence.log"

# Optional: Keep a console logger for debugging output in terminal
console = logging.getLogger("occurrence_console")
console.setLevel(logging.INFO)
if not console.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
    console.addHandler(sh)


# -------------------------------------------------------
# Helper: Write to File
# -------------------------------------------------------
def clear_logs():
    """Truncates the log file and starts fresh."""
    _log("=" * 80, mode="w")
    _log("LOG RESET | STARTING NEW RUN", mode="a")


def _log(message: str, mode: str = "a"):
    """
    Writes message to log file.
    mode='w' -> overwrites file (start of new request)
    mode='a' -> appends to file (subsequent steps)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | INFO     | {message}\n"
    
    try:
        with open(LOG_FILE, mode, encoding="utf-8") as f:
            f.write(line)
        # Also print to console
        # print(line.strip()) 
    except Exception as e:
        console.error(f"Failed to write to {LOG_FILE}: {e}")


HIGH_SCORE_NEGATIVE_HINTS = ["no ", "none", "stable", "isolated", "not ", "no history", "no finding"]
LOW_SCORE_POSITIVE_HINTS  = ["major", "failed", "critical", "systemic", "chronic", "ineffective", "defect"]


def _check_consistency(code: str, score: int, evidence: str) -> str:
    if not evidence or evidence.strip() == "":
        return "NO_EVIDENCE"
    ev_lower = evidence.lower()
    if score >= 7:
        for hint in HIGH_SCORE_NEGATIVE_HINTS:
            if hint in ev_lower:
                return f"REVIEW  <-- Score is HIGH ({score}) but evidence contains '{hint.strip()}'"
    if score <= 3:
        for hint in LOW_SCORE_POSITIVE_HINTS:
            if hint in ev_lower:
                return f"REVIEW  <-- Score is LOW ({score}) but evidence contains '{hint}'"
    return "OK"


# -------------------------------------------------------
# STEP 1 — API Request (Truncates file!)
# -------------------------------------------------------
def log_request(complaint_id: str, product: str, source: str,
                date: str, num_similar_cases: int, has_pattern_data: bool = False):
    # FORCE OVERWRITE MODE ('w') for the first step
    _log("=" * 80, mode="w")
    _log("[STEP 1] API REQUEST RECEIVED", mode="a")
    _log(f"  Complaint ID      : {complaint_id}")
    _log(f"  Product           : {product}")
    _log(f"  Source            : {source}")
    _log(f"  Date              : {date}")
    _log(f"  Similar Cases     : {num_similar_cases} case(s) provided")
    _log(f"  Pattern Data      : {'Yes' if has_pattern_data else 'No'}")
    _log(f"  Timestamp         : {datetime.now().isoformat()}")


# -------------------------------------------------------
# NODE LIFECYCLE — Start / End (DO #7 Observability)
# -------------------------------------------------------
def log_node_start(node_name: str):
    """Log when a node begins execution."""
    _log("-" * 80)
    _log(f"[NODE START] >>> {node_name.upper()} | {datetime.now().isoformat()}")


def log_node_end(node_name: str, output_summary: str = ""):
    """Log when a node finishes execution."""
    _log(f"[NODE END]   <<< {node_name.upper()} | {datetime.now().isoformat()}")
    if output_summary:
        _log(f"  Output: {output_summary}")


# -------------------------------------------------------
# STEP 2 — Full Prompt
# -------------------------------------------------------
def log_prompt(prompt: str):
    _log("-" * 80)
    _log("[STEP 2] FULL PROMPT SENT TO LLM")
    _log(f"  Prompt Length     : {len(prompt)} characters")
    _log("  --- PROMPT START ---")
    for line in prompt.splitlines():
        _log(f"  {line}")
    _log("  --- PROMPT END ---")


# -------------------------------------------------------
# STEP 3 — Raw Response
# -------------------------------------------------------
def log_raw_response(raw: str, run_number: int = 1):
    _log("-" * 80)
    _log(f"[STEP 3] RAW LLM RESPONSE — Run {run_number} (before parsing)")
    _log(f"  Response Length   : {len(raw)} characters")
    _log("  --- RESPONSE START ---")
    for line in raw.splitlines():
        _log(f"  {line}")
    _log("  --- RESPONSE END ---")


# -------------------------------------------------------
# STEP 4 — Score Audit
# -------------------------------------------------------
def log_score_audit(scores: dict, similar_cases: list):
    # Load metrics dynamically — single source of truth from metrics.json
    parameters = load_metrics.invoke({}).get("parameters", {})

    _log("-" * 80)
    _log("[STEP 4] SCORE AUDIT — LLM SCORE vs RUBRIC vs INPUT EVIDENCE")
    _log("  (Use REVIEW flags to spot potential hallucinations)")
    _log("")

    all_factors: dict[str, list[str]] = {}
    for case in similar_cases:
        factors = case.get("occurrence_factors", {})
        for key, val in factors.items():
            all_factors.setdefault(key, []).append(f"[{case.get('case_id','?')}] {val}")

    for code, param in parameters.items():
        score = scores.get(code, "?")
        levels = {int(k): v for k, v in param["levels"].items()}
        rubric_text = levels.get(score, "Unknown score") if isinstance(score, int) else "N/A"
        factor_key = param["name"]   # name == factor_key (same string)
        evidence_list = all_factors.get(factor_key, [])
        evidence_str = " | ".join(evidence_list) if evidence_list else "(no occurrence_factors provided)"
        consistency = _check_consistency(code, score, evidence_str) if isinstance(score, int) else "N/A"

        _log(f"  [{code}] {param['name']}")
        _log(f"    Score Given     : {score}/10")
        _log(f"    Rubric (score {score}): {rubric_text}")
        _log(f"    Input Evidence  : {evidence_str}")
        _log(f"    Consistency     : {consistency}")
        _log("")

    reasoning = scores.get("reasoning", "")
    if reasoning:
        _log(f"  LLM Reasoning   : {reasoning}")
        _log("")


# -------------------------------------------------------
# STEP 5 — Weighted Calc
# -------------------------------------------------------
def log_weighted_calculation(scores, weights: dict):
    # Load metrics dynamically — single source of truth from metrics.json
    parameters = load_metrics.invoke({}).get("parameters", {})

    _log("-" * 80)
    _log("[STEP 5] WEIGHTED SCORE CALCULATION")
    _log(f"  {'Code':<5} {'Parameter':<48} {'Score':>5} {'Weight':>7} {'Contribution':>13}")
    _log(f"  {'-'*5} {'-'*48} {'-'*5} {'-'*7} {'-'*13}")

    score_map = {
        "HF": scores.HF, "TR": scores.TR, "PS": scores.PS,
        "PC": scores.PC, "DM": scores.DM, "SY": scores.SY,
        "OE": scores.OE, "CA": scores.CA, "SU": scores.SU,
        "AU": scores.AU,
    }
    total = 0.0
    for code, param in parameters.items():
        score = score_map.get(code, 0)
        weight = weights.get(code, param["weight"])
        contribution = score * weight
        total += contribution
        _log(
            f"  {code:<5} {param['name']:<48} {score:>5} "
            f"{weight*100:>6.0f}%  {contribution:>12.4f}"
        )

    _log(f"  {'':5} {'':48} {'':5} {'':7} {'─'*13}")
    _log(f"  {'':5} {'TOTAL WEIGHTED SCORE':<48} {'':5} {'100%':>7} {total:>12.4f}")
    _log(f"  Rounded Score     : {max(1, min(10, int(round(total))))}")


# -------------------------------------------------------
# STEP 6 — Final Output
# -------------------------------------------------------
def log_final_output(complaint_id: str, weighted_score: float, rating: str):
    _log("-" * 80)
    _log("[STEP 6] FINAL OUTPUT")
    _log(f"  Complaint ID      : {complaint_id}")
    _log(f"  Weighted Score    : {weighted_score}")
    _log(f"  Rating            : {rating}")
    _log("=" * 80)


def log_error(location: str, error: str):
    _log(f"[ERROR] {location}: {error}")
