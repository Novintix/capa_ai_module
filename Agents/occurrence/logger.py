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

# -------------------------------------------------------
# Setup
# -------------------------------------------------------
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
LOG_FILE = log_dir / "occurrence.log"
NUM_RUNS = 1  # Single-run with evidence-first anchoring (Option G)

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


# -------------------------------------------------------
# Metric metadata — mirrors metrics.json exactly
# -------------------------------------------------------
METRIC_META = {
    "HF": {
        "name": "Historical Frequency of Events",
        "weight": 0.18,
        "factor_key": "Historical Frequency of Events",
        "levels": {
            1: "No history of events (0 occurrences in last 3-5 years)",
            2: "1 isolated event, no recurrence",
            3: "1-2 events; no trend",
            4: "2-3 events sporadically",
            5: "Recurs quarterly or similar frequency",
            6: "Recurs monthly",
            7: "Recurs multiple times monthly",
            8: "Recurs weekly",
            9: "Recurs several times per week",
            10: "Recurs daily or every cycle/run",
        }
    },
    "TR": {
        "name": "Trend Analysis / Pattern Recognition",
        "weight": 0.12,
        "factor_key": "Trend Analysis / Pattern Recognition",
        "levels": {
            1: "No trend; stable flat data",
            2: "Minor fluctuation but no upward trend",
            3: "One short-term spike, not repeated",
            4: "Weak increasing tendency",
            5: "Small but noticeable trend signal",
            6: "Clear visible upward trend",
            7: "Strong accelerating trend",
            8: "Recurring trend peaks",
            9: "Persistent accelerating trend",
            10: "Uncontrolled exponential trend",
        }
    },
    "PS": {
        "name": "Process Stability / Cp-Cpk Variability",
        "weight": 0.10,
        "factor_key": "Process Stability / Cp-Cpk Variability",
        "levels": {
            1: "High stability (Cp/Cpk > 2.0)",
            2: "Cp/Cpk 1.67-2.0",
            3: "Cp/Cpk 1.33-1.67",
            4: "Cp/Cpk 1.1-1.33",
            5: "Cp/Cpk at minimum acceptable (1.0-1.1)",
            6: "Cp/Cpk below requirement (<1.0)",
            7: "Significant variation; unstable",
            8: "Chronic variability",
            9: "Out-of-control process",
            10: "Process failure almost guaranteed",
        }
    },
    "PC": {
        "name": "Effectiveness of Preventive Controls",
        "weight": 0.12,
        "factor_key": "Effectiveness of Preventive Controls",
        "levels": {
            1: "Highly effective controls; proven elimination",
            2: "Strong controls, minimal risk",
            3: "Controls adequate with minor gaps",
            4: "Acceptable but partially effective",
            5: "Controls reduce but do not prevent occurrence",
            6: "Controls inconsistently effective",
            7: "Controls weak; high recurrence probability",
            8: "Preventive controls largely ineffective",
            9: "No functional preventive controls",
            10: "No controls exist or controls cannot be applied",
        }
    },
    "DM": {
        "name": "Effectiveness of Detection / Monitoring",
        "weight": 0.10,
        "factor_key": "Effectiveness of Detection / Monitoring",
        "levels": {
            1: "Automated 100% detection; real-time",
            2: "Very high detection reliability (>=95%)",
            3: "Reliable manual/automated detection",
            4: "Moderate detection capability",
            5: "Detection identifies only some issues",
            6: "Low detection reliability",
            7: "Detection unreliable; major gaps",
            8: "Detection seldom effective",
            9: "Almost undetectable failures",
            10: "Cannot detect until after failure / field complaint",
        }
    },
    "SY": {
        "name": "Systemic vs Isolated Issue",
        "weight": 0.12,
        "factor_key": "Systemic vs Isolated Issue",
        "levels": {
            1: "Proven isolated root cause",
            2: "Very low systemic probability",
            3: "Mostly isolated with minimal spread",
            4: "Potential systemic contributors",
            5: "Mixed root causes; recurring",
            6: "Recurrence suggests systemic risk",
            7: "Systemic confirmed across products/lines",
            8: "Widespread systemic behavior",
            9: "Major systemic failure",
            10: "Fully systemic and uncontained",
        }
    },
    "OE": {
        "name": "Operator / Equipment Factors",
        "weight": 0.08,
        "factor_key": "Operator / Equipment Factors",
        "levels": {
            1: "No operator/equipment involvement",
            2: "Extremely rare operator/equipment errors",
            3: "Minor isolated errors",
            4: "Occasional operator/equipment fluctuations",
            5: "Regular but manageable impacts",
            6: "Frequent operator/equipment error contribution",
            7: "Known failure mode tied to human or equipment",
            8: "Chronic operator or equipment issues",
            9: "Multiple unresolved causes",
            10: "Unavoidable failure without redesign",
        }
    },
    "CA": {
        "name": "CAPA / Past Corrective Actions Effectiveness",
        "weight": 0.08,
        "factor_key": "CAPA / Past Corrective Actions Effectiveness",
        "levels": {
            1: "CAPA permanently resolved issue",
            2: "CAPA highly effective; no recurrence",
            3: "Minor recurrence but controlled",
            4: "CAPA partially effective",
            5: "Recurrence observed despite CAPA",
            6: "CAPA weaknesses confirmed",
            7: "Recurring CAPA cycles required",
            8: "CAPAs repeatedly failed",
            9: "Major CAPA failure / systemic flaws",
            10: "No CAPA applicable or failed continuously",
        }
    },
    "SU": {
        "name": "Supplier / External Factors",
        "weight": 0.05,
        "factor_key": "Supplier / External Factors",
        "levels": {
            1: "Supplier process stable; no history",
            2: "Rare supplier issues",
            3: "Minor variations manageable",
            4: "Occasional supplier impact",
            5: "Noticeable supplier variability",
            6: "Supplier instability visible",
            7: "Frequent supplier-driven failures",
            8: "Chronic supplier quality problems",
            9: "Major supplier fails capability requirements",
            10: "Supplier environment uncontrollable",
        }
    },
    "AU": {
        "name": "Audit / Compliance Findings",
        "weight": 0.05,
        "factor_key": "Audit / Compliance Findings",
        "levels": {
            1: "No audit findings; full compliance",
            2: "Very minor observations",
            3: "Low-severity documented finding",
            4: "Observations requiring minor action",
            5: "Noted risk requiring monitoring",
            6: "Repeated audit findings",
            7: "Significant observations",
            8: "Major regulatory findings (e.g., 483/audit major)",
            9: "Systemic non-compliance",
            10: "Enforcement/critical shutdown level",
        }
    },
}

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
                date: str, num_similar_cases: int):
    # FORCE OVERWRITE MODE ('w') for the first step
    _log("=" * 80, mode="w")
    _log("[STEP 1] API REQUEST RECEIVED", mode="a")
    _log(f"  Complaint ID      : {complaint_id}")
    _log(f"  Product           : {product}")
    _log(f"  Source            : {source}")
    _log(f"  Date              : {date}")
    _log(f"  Similar Cases     : {num_similar_cases} case(s) provided")
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
    _log(f"[STEP 3] RAW LLM RESPONSE — Run {run_number} of {NUM_RUNS} (before parsing)")
    _log(f"  Response Length   : {len(raw)} characters")
    _log("  --- RESPONSE START ---")
    for line in raw.splitlines():
        _log(f"  {line}")
    _log("  --- RESPONSE END ---")


# -------------------------------------------------------
# STEP 4 — Score Audit
# -------------------------------------------------------
def log_score_audit(scores: dict, similar_cases: list):
    _log("-" * 80)
    _log("[STEP 4] SCORE AUDIT — LLM SCORE vs RUBRIC vs INPUT EVIDENCE")
    _log("  (Use REVIEW flags to spot potential hallucinations)")
    _log("")

    all_factors: dict[str, list[str]] = {}
    for case in similar_cases:
        factors = case.get("occurrence_factors", {})
        for key, val in factors.items():
            all_factors.setdefault(key, []).append(f"[{case.get('case_id','?')}] {val}")

    for code, meta in METRIC_META.items():
        score = scores.get(code, "?")
        rubric_text = meta["levels"].get(score, "Unknown score") if isinstance(score, int) else "N/A"
        factor_key = meta["factor_key"]
        evidence_list = all_factors.get(factor_key, [])
        evidence_str = " | ".join(evidence_list) if evidence_list else "(no occurrence_factors provided)"
        consistency = _check_consistency(code, score, evidence_str) if isinstance(score, int) else "N/A"

        _log(f"  [{code}] {meta['name']}")
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
    for code, meta in METRIC_META.items():
        score = score_map.get(code, 0)
        weight = weights.get(code, meta["weight"])
        contribution = score * weight
        total += contribution
        _log(
            f"  {code:<5} {meta['name']:<48} {score:>5} "
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
