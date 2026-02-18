"""
logger.py

Deep Audit Logger for the Occurrence Agent.

Logs every step in detail to help detect LLM hallucinations:
  STEP 1 — API request (who called, what complaint)
  STEP 2 — Full prompt sent to LLM
  STEP 3 — Raw LLM response (before any parsing)
  STEP 4 — Score audit: for each parameter, logs:
              - Score given by LLM
              - Rubric description for that score (what score X means)
              - Input evidence from occurrence_factors
              - Consistency flag (does rubric match evidence?)
  STEP 5 — Weighted calculation (score × weight = contribution)
  STEP 6 — Final output

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

logger = logging.getLogger("occurrence_agent")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    log_file = log_dir / "occurrence.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


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

# Simple keyword hints per score band for consistency checking
# If score >= 7 but evidence has "no", "none", "stable", "isolated" → flag
HIGH_SCORE_NEGATIVE_HINTS = ["no ", "none", "stable", "isolated", "not ", "no history", "no finding"]
# If score <= 3 but evidence has "major", "failed", "critical", "systemic" → flag
LOW_SCORE_POSITIVE_HINTS  = ["major", "failed", "critical", "systemic", "chronic", "ineffective", "defect"]


def _check_consistency(code: str, score: int, evidence: str) -> str:
    """
    Simple heuristic consistency check.
    Returns 'OK', 'REVIEW' (possible hallucination), or 'NO_EVIDENCE'.
    """
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
# STEP 1 — API Request
# -------------------------------------------------------
def log_request(complaint_id: str, product: str, source: str,
                date: str, num_similar_cases: int):
    logger.info("=" * 80)
    logger.info("[STEP 1] API REQUEST RECEIVED")
    logger.info(f"  Complaint ID      : {complaint_id}")
    logger.info(f"  Product           : {product}")
    logger.info(f"  Source            : {source}")
    logger.info(f"  Date              : {date}")
    logger.info(f"  Similar Cases     : {num_similar_cases} case(s) provided")
    logger.info(f"  Timestamp         : {datetime.now().isoformat()}")


# -------------------------------------------------------
# STEP 2 — Full Prompt Sent to LLM
# -------------------------------------------------------
def log_prompt(prompt: str):
    logger.info("-" * 80)
    logger.info("[STEP 2] FULL PROMPT SENT TO LLM")
    logger.info(f"  Prompt Length     : {len(prompt)} characters")
    logger.info("  --- PROMPT START ---")
    for line in prompt.splitlines():
        logger.info(f"  {line}")
    logger.info("  --- PROMPT END ---")


# -------------------------------------------------------
# STEP 3 — Raw LLM Response
# -------------------------------------------------------
def log_raw_response(raw: str):
    logger.info("-" * 80)
    logger.info("[STEP 3] RAW LLM RESPONSE (before parsing)")
    logger.info(f"  Response Length   : {len(raw)} characters")
    logger.info("  --- RESPONSE START ---")
    for line in raw.splitlines():
        logger.info(f"  {line}")
    logger.info("  --- RESPONSE END ---")


# -------------------------------------------------------
# STEP 4 — Score Audit (per parameter)
# -------------------------------------------------------
def log_score_audit(scores: dict, similar_cases: list):
    """
    For each of the 10 parameters:
      - Log the score the LLM gave
      - Log what that score MEANS (rubric description)
      - Log the input evidence from occurrence_factors across all similar cases
      - Flag if the score looks inconsistent with the evidence
    """
    logger.info("-" * 80)
    logger.info("[STEP 4] SCORE AUDIT — LLM SCORE vs RUBRIC vs INPUT EVIDENCE")
    logger.info("  (Use REVIEW flags to spot potential hallucinations)")
    logger.info("")

    # Collect all occurrence_factors evidence across similar cases
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

        logger.info(f"  [{code}] {meta['name']}")
        logger.info(f"    Score Given     : {score}/10")
        logger.info(f"    Rubric (score {score}): {rubric_text}")
        logger.info(f"    Input Evidence  : {evidence_str}")
        logger.info(f"    Consistency     : {consistency}")
        logger.info("")

    reasoning = scores.get("reasoning", "")
    if reasoning:
        logger.info(f"  LLM Reasoning   : {reasoning}")
        logger.info("")


# -------------------------------------------------------
# STEP 5 — Weighted Calculation
# -------------------------------------------------------
def log_weighted_calculation(scores, weights: dict):
    logger.info("-" * 80)
    logger.info("[STEP 5] WEIGHTED SCORE CALCULATION")
    logger.info(f"  {'Code':<5} {'Parameter':<48} {'Score':>5} {'Weight':>7} {'Contribution':>13}")
    logger.info(f"  {'-'*5} {'-'*48} {'-'*5} {'-'*7} {'-'*13}")

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
        logger.info(
            f"  {code:<5} {meta['name']:<48} {score:>5} "
            f"{weight*100:>6.0f}%  {contribution:>12.4f}"
        )

    logger.info(f"  {'':5} {'':48} {'':5} {'':7} {'─'*13}")
    logger.info(f"  {'':5} {'TOTAL WEIGHTED SCORE':<48} {'':5} {'100%':>7} {total:>12.4f}")
    logger.info(f"  Rounded Score     : {max(1, min(10, int(round(total))))}")


# -------------------------------------------------------
# STEP 6 — Final Output
# -------------------------------------------------------
def log_final_output(complaint_id: str, weighted_score: float, rating: str):
    logger.info("-" * 80)
    logger.info("[STEP 6] FINAL OUTPUT")
    logger.info(f"  Complaint ID      : {complaint_id}")
    logger.info(f"  Weighted Score    : {weighted_score}")
    logger.info(f"  Rating            : {rating}")
    logger.info("=" * 80)


# -------------------------------------------------------
# Helpers kept for backward compatibility
# -------------------------------------------------------
def log_prompt_built(description: str, num_similar_cases: int, has_custom_metrics: bool):
    """Lightweight summary log (used when full prompt log is not needed)."""
    logger.info("-" * 80)
    logger.info("[STEP 2] PROMPT BUILT")
    logger.info(f"  Description       : {description[:120]}{'...' if len(description) > 120 else ''}")
    logger.info(f"  Similar Cases     : {num_similar_cases} injected into prompt")
    logger.info(f"  Metrics Source    : {'Custom (uploaded)' if has_custom_metrics else 'Default metrics.json'}")
    logger.info(f"  Parameters        : {', '.join(METRIC_META.keys())} (10 total)")


def log_llm_scores(scores: dict):
    """Simple score table (Step 3 summary, used before full audit)."""
    logger.info("-" * 80)
    logger.info("[STEP 3] LLM SCORES RECEIVED")
    logger.info(f"  {'Code':<5} {'Parameter':<48} {'Score':>5}")
    logger.info(f"  {'-'*5} {'-'*48} {'-'*5}")
    for code, meta in METRIC_META.items():
        score = scores.get(code, "?")
        logger.info(f"  {code:<5} {meta['name']:<48} {score:>5}")
    reasoning = scores.get("reasoning", "")
    if reasoning:
        logger.info(f"\n  Reasoning: {reasoning}")


def log_error(location: str, error: str):
    logger.error(f"[ERROR] {location}: {error}")
