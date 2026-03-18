"""
risk_analysis_orchestrator_service/payloads.py

Per-agent payload builders for the O2 Risk Analysis Orchestrator.

HOW TO USE:
  - Each function accepts (e: dict, issue: str) and returns a dict
    matching the exact state schema expected by the sub-agent.
  - To add a new agent → add a new function here and call it in build_all_payloads().
  - To change a payload schema → edit only the relevant function here.

Functions:
    detection_payload(e, issue)   → A5 Detection Agent
    pattern_payload(e, issue)     → A2 Pattern Agent
    severity_payload(e, issue)    → A3 Severity Agent
    similar_cases_payload(issue)  → A1 Similar Cases Agent
    occurrence_payload(e, issue)  → A4 Occurrence Agent
    regulatory_payload(e, issue)  → A6 Regulatory Agent
    meta_payload(e, issue, state) → Meta block used by A7 and finalize

    build_all_payloads(e, issue, state) → full enriched_inputs dict
"""

from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# A5 — Detection Agent Payload
# Matches: Agents/detection/state.py → AgentState
# ══════════════════════════════════════════════════════════════════════════════

def detection_payload(e: dict, issue: str) -> dict:
    return {
        "complaint_id":          e.get("complaint_id", "UNKNOWN"),
        "complaint_source":      e.get("source", "manual"),
        "complaint_description": issue,
        "policy_document_path":  None,
        "has_policy":            False,
        "iteration":             0,
        "max_iterations":        3,
    }


# ══════════════════════════════════════════════════════════════════════════════
# A2 — Pattern Agent Payload
# Matches: Agents/pattern/state.py → AgentState
# ══════════════════════════════════════════════════════════════════════════════

def pattern_payload(e: dict, issue: str) -> dict:
    return {
        "complaint_id":          e.get("complaint_id", "UNKNOWN"),
        "complaint_description": issue,
        "product_family":        e.get("product"),
        "region":                e.get("region"),
        "severity":              e.get("severity_hint"),
        "site":                  None,
        "company_id":            None,
        "company_schema":        None,
        "historical_complaints": [],
        "matched_complaint_ids": [],
        "iteration":             0,
        "max_iterations":        3,
        "next_step":             "fetch_historical",
    }


# ══════════════════════════════════════════════════════════════════════════════
# A3 — Severity Agent Payload
# Matches: Agents/severity/state.py → SeverityState
# ══════════════════════════════════════════════════════════════════════════════

def severity_payload(e: dict, issue: str) -> dict:
    return {
        "issue": issue,
    }


# ══════════════════════════════════════════════════════════════════════════════
# A1 — Similar Cases Agent Payload
# Matches: Agents/similar_cases/state.py → SimilarCasesState
# ══════════════════════════════════════════════════════════════════════════════

def similar_cases_payload(issue: str) -> dict:
    return {
        "input": {
            "query": issue
        },
        "iteration": 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# A4 — Occurrence Agent Payload
# Matches: Agents/occurrence/state.py → OccurrenceState
# ══════════════════════════════════════════════════════════════════════════════

def occurrence_payload(e: dict, issue: str) -> dict:
    return {
        "input": {
            "complaint_id":       e.get("complaint_id", "UNKNOWN"),
            "description":        issue,
            "source":             e.get("source", "manual"),
            "date":               e.get("date", "unknown"),
            "product":            e.get("product", "unknown"),
            "similar_cases":      [],
            "additional_context": e.get("suspected_cause"),
        },
        "iteration": 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# A6 — Regulatory Agent Payload
# Matches: Agents/regulatory/state.py → AgentState
# ══════════════════════════════════════════════════════════════════════════════

def regulatory_payload(e: dict, issue: str) -> dict:
    return {
        "complaint_id":       e.get("complaint_id", "UNKNOWN"),
        "description":        issue,
        "date_of_awareness":  e.get("date", "unknown"),
        "product_type":       e.get("product_type"),
        "market_country":     e.get("market_country"),
        "severity":           e.get("severity_hint"),
        "issue_type":         e.get("issue_type"),
        "death_or_injury":    e.get("death_or_injury", False),
        "batch_number":       e.get("batch_number"),
        "iteration":          0,
        "max_iterations":     3,
    }


# ══════════════════════════════════════════════════════════════════════════════
# META — used by A7 (AI Reasoning) and finalize_node
# Not sent to any sub-agent directly.
# ══════════════════════════════════════════════════════════════════════════════

def meta_payload(e: dict, issue: str, state: Any) -> dict:
    return {
        "urgency":   state.get("urgency", False),
        "issue":     issue,
        "extracted": e,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN BUILDER — called by payload_builder_node in orchestrator.py
# Returns the full enriched_inputs dict.
# Add a new agent → add its payload function above, then wire it in here.
# ══════════════════════════════════════════════════════════════════════════════

def build_all_payloads(e: dict, issue: str, state: Any) -> dict:
    """
    Assembles all agent payloads into one enriched_inputs dict.

    Args:
        e     : Extracted context dict from context_node (LLM output)
        issue : The core issue string (from e or raw_input)
        state : Full orchestrator state (for urgency, etc.)

    Returns:
        enriched_inputs dict with keys: detection, pattern, severity,
        similar_cases, occurrence, regulatory, _meta
    """
    return {
        "detection":     detection_payload(e, issue),
        "pattern":       pattern_payload(e, issue),
        "severity":      severity_payload(e, issue),
        "similar_cases": similar_cases_payload(issue),
        "occurrence":    occurrence_payload(e, issue),
        "regulatory":    regulatory_payload(e, issue),
        "_meta":         meta_payload(e, issue, state),
    }
