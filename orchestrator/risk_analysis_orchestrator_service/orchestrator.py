"""
orchestrator_service/orchestrator.py

Risk Analysis Orchestrator (O2)

Flow:
    START
      ↓
    input_validator        ← LLM-based guardrail
      ├── malicious/terminated → END
      ├── awaiting_correction  → request_correction_node → END (paused)
      └── passed               → context_node
                                    └── payload_builder_node
                                          └── [A5|A1|A2|A3] parallel fan-out
                                                └── A4 occurrence (fan-in)
                                                      └── rpn_calculator_node
                                                            └── A6 regulatory
                                                                  └── A7 reasoning
                                                                        └── finalize_node
                                                                              └── END

Serialization strategy
──────────────────────
The occurrence sub-graph returns:

    OccurrenceState {
        final_output: OccurrenceOutput {
            weighted_score: int,
            rating: str,
            breakdown: OccurrenceScoreResponse {   ← nested Pydantic model
                scores: Dict[str, int],
                reasoning: str
            }
        }
    }

Three layers of Pydantic nesting.  model_dump() without mode="json" does NOT
recursively convert nested models in Pydantic v1 and is unreliable in v2 for
custom __getattr__ models.  We use deep_serialize() which:

  1. Tries model_dump(mode="json")  — Pydantic v2, converts everything
  2. Falls back to .dict()          — Pydantic v1
  3. Recurses into every dict/list  — catches any surviving nested objects
  4. Converts datetime → ISO string
  5. Returns primitives unchanged

deep_serialize() is applied to EVERY graph.invoke() result at the call site.
"""

import json
import operator
import datetime
from typing import Annotated, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from Agents.detection.graph     import create_detection_graph  as build_detection_graph
from Agents.pattern.graph       import create_pattern_graph    as build_pattern_graph
from Agents.severity.graph      import build_graph             as build_severity_graph
from Agents.occurrence.graph    import occurrence_graph
from Agents.regulatory.graph    import create_regulatory_graph as build_regulatory_graph
from Agents.aireasoning.graph   import aireasoning_graph
from Agents.similar_cases.graph import similar_cases_graph

from config.aws_bedrock_config import get_llm
from .prompts  import EXTRACTION_PROMPT, VALIDATION_PROMPT, SAFETY_CHECK_PROMPT
from .payloads import build_all_payloads
from .state    import RiskAnalysisState


# ══════════════════════════════════════════════════════════════════════════════
# REDIS — use centralised config (reads REDIS_URL from .env)
# ══════════════════════════════════════════════════════════════════════════════

from config.redis_config import redis_client, REDIS_URL, write_agent_status, publish_agent_event  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

MAX_CORRECTION_ATTEMPTS = 3


# ══════════════════════════════════════════════════════════════════════════════
# SERIALIZATION UTILITY
#
# deep_serialize(obj) — single function, replaces the previous two-function
# approach. Applied to every graph.invoke() result before writing to state.
#
# Problem this solves:
#   OccurrenceOutput.breakdown is OccurrenceScoreResponse (nested Pydantic).
#   model_dump() called on OccurrenceOutput returns:
#       {"weighted_score": 7, "rating": "HIGH",
#        "breakdown": OccurrenceScoreResponse(...)}   ← still a Pydantic object!
#   because model_dump() in some Pydantic versions does not recursively
#   convert nested models that have custom __getattr__ or are v1 models.
#
# Solution:
#   deep_serialize() checks hasattr(obj, "model_dump") OR hasattr(obj, "dict")
#   at EVERY level of recursion — not just the top level.
#   So OccurrenceScoreResponse inside the breakdown dict is caught and
#   converted on the recursive call, regardless of nesting depth.
#
#   For Pydantic v2 we use model_dump(mode="json") which also converts
#   datetime fields embedded inside the model to ISO strings in one shot.
#   For Pydantic v1 we use .dict() and let the datetime branch handle any
#   surviving datetime objects on the next recursive pass.
# ══════════════════════════════════════════════════════════════════════════════

def deep_serialize(obj):
    """
    Recursively converts any object to a JSON-serializable form.

    Conversion order (checked at every level of recursion):
      1. datetime.datetime / datetime.date  → ISO 8601 string
      2. Pydantic v2 (.model_dump)          → dict via model_dump(mode="json"),
                                              then recurse into the result
      3. Pydantic v1 (.dict)                → dict via .dict(),
                                              then recurse into the result
      4. dict                               → recurse into values
      5. list / tuple                       → recurse into items
      6. primitives                         → return unchanged

    Why recurse AFTER model_dump?
      model_dump(mode="json") converts top-level fields but may leave
      nested Pydantic models (e.g. OccurrenceScoreResponse inside
      OccurrenceOutput.breakdown) as raw objects if the outer model
      was constructed with nested model instances rather than dicts.
      The recursive call catches those survivors.
    """
    # ── datetime ─────────────────────────────────────────────────────────────
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()

    # ── Pydantic v2 ──────────────────────────────────────────────────────────
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            dumped = obj.model_dump(mode="json")
        except Exception:
            try:
                dumped = obj.model_dump()
            except Exception:
                return str(obj)
        return deep_serialize(dumped)

    # ── Pydantic v1 ──────────────────────────────────────────────────────────
    if hasattr(obj, "dict") and callable(obj.dict):
        # Guard: only call .dict() on actual Pydantic models, not plain dicts
        # (plain dicts also have a .values() method but not .dict())
        try:
            dumped = obj.dict()
            return deep_serialize(dumped)
        except Exception:
            pass

    # ── dict ─────────────────────────────────────────────────────────────────
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}

    # ── list / tuple ─────────────────────────────────────────────────────────
    if isinstance(obj, (list, tuple)):
        return [deep_serialize(v) for v in obj]

    # ── primitive ─────────────────────────────────────────────────────────────
    return obj


def _now() -> str:
    """Returns current timestamp as ISO string — safe for Redis/JSON."""
    return datetime.datetime.now().isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# NODE 0 — INPUT VALIDATOR
# LLM gatekeeper — rejects malicious, irrelevant, or vague inputs.
# Correctable failures → request_correction_node (user can retry).
# Malicious / max-attempts → hard END.
# ══════════════════════════════════════════════════════════════════════════════

def input_validator(state: RiskAnalysisState) -> dict:
    print("\n[STEP 0] 🔍 Input Validator: checking input with LLM guardrails...")

    raw              = state.get("raw_input", "").strip()
    correction_count = state.get("correction_count", 0)

    # ── Hard stop: too many failed attempts ──────────────────────────────────
    if correction_count >= MAX_CORRECTION_ATTEMPTS:
        print(f"   ✗ Max correction attempts ({MAX_CORRECTION_ATTEMPTS}) reached")
        return {
            "validation_passed":   False,
            "validation_error":    f"Maximum {MAX_CORRECTION_ATTEMPTS} correction attempts reached. Workflow terminated.",
            "validation_category": "terminated",
            "awaiting_correction": False,
            "correction_message":  None,
            "node_log": [{"node": "input_validator", "status": "terminated",
                          "reason": "max_attempts", "attempt": correction_count,
                          "timestamp": _now()}],
        }

    # ── Trivial check before wasting an LLM call ─────────────────────────────
    if not raw or len(raw) < 10:
        msg = (
            "Your input is too short. Please describe the medical device issue "
            "in detail (minimum 10 characters)."
        )
        print("   ✗ Input too short")
        return {
            "validation_passed":   False,
            "validation_error":    "Input too short.",
            "validation_category": "irrelevant",
            "awaiting_correction": True,
            "correction_message":  msg,
            "correction_count":    correction_count + 1,
            "node_log": [{"node": "input_validator", "status": "awaiting_correction",
                          "reason": "too_short", "attempt": correction_count + 1,
                          "timestamp": _now()}],
        }

    # ── LLM deep validation ──────────────────────────────────────────────────
    try:
        llm    = get_llm()
        resp   = llm.invoke(f"{VALIDATION_PROMPT}\n\nClient Input: {raw}")
        clean  = resp.content.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(clean)
    except Exception as exc:
        print(f"   ⚠ Validator LLM error: {exc}")
        return {
            "validation_passed":   False,
            "validation_error":    "System error during validation. Please try again.",
            "validation_category": "error",
            "awaiting_correction": True,
            "correction_message":  "A system error occurred while validating your input. Please try submitting again.",
            "correction_count":    correction_count + 1,
            "node_log": [{"node": "input_validator", "status": "error",
                          "reason": str(exc), "attempt": correction_count + 1,
                          "timestamp": _now()}],
        }

    is_valid = parsed.get("is_valid", False)
    reason   = parsed.get("reason", "Unknown validation failure")
    category = parsed.get("category", "irrelevant")

    # ── Passed ────────────────────────────────────────────────────────────────
    if is_valid:
        print(f"   ✓ Validation passed (category: {category})")
        return {
            "validation_passed":   True,
            "validation_error":    None,
            "validation_category": category,
            "awaiting_correction": False,
            "correction_message":  None,
            "node_log": [{"node": "input_validator", "status": "passed",
                          "category": category, "timestamp": _now()}],
        }

    # ── Failed — determine if correctable ────────────────────────────────────
    # malicious  → hard terminate (no retry)
    # irrelevant / vague / error → soft fail (user can correct)
    is_malicious        = category == "malicious"
    awaiting_correction = not is_malicious

    correction_messages = {
        "irrelevant": (
            "Your input does not appear to be related to a medical device quality "
            "issue or CAPA. Please describe a specific device complaint, manufacturing "
            "non-conformance, or patient safety event."
        ),
        "error": "Validation encountered an issue. Please rephrase and try again.",
    }
    correction_msg = correction_messages.get(
        category,
        f"Input rejected: {reason}. Please revise your description and try again."
    )

    print(f"   ✗ Validation failed: {reason} (category: {category}, correctable: {awaiting_correction})")

    return {
        "validation_passed":   False,
        "validation_error":    reason,
        "validation_category": category,
        "awaiting_correction": awaiting_correction,
        "correction_message":  correction_msg if awaiting_correction else None,
        "correction_count":    correction_count + 1,
        "node_log": [{"node": "input_validator",
                      "status": "awaiting_correction" if awaiting_correction else "rejected",
                      "category": category, "reason": reason,
                      "attempt": correction_count + 1,
                      "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 0b — REQUEST CORRECTION NODE
# Writes correction_response to state.
# router.py reads this key and returns it as the API response body —
# visible in both Postman and Streamlit immediately.
# Workflow ends here — resumes via POST /capa/correct/{thread_id}.
# ══════════════════════════════════════════════════════════════════════════════

def request_correction_node(state: RiskAnalysisState) -> dict:
    print("\n[STEP 0b] 💬 Request Correction Node: surfacing correction to user...")

    correction_count = state.get("correction_count", 1)
    remaining        = MAX_CORRECTION_ATTEMPTS - correction_count

    correction_response = {
        "status":              "awaiting_correction",
        "correction_message":  state.get("correction_message"),
        "validation_error":    state.get("validation_error"),
        "validation_category": state.get("validation_category"),
        "attempts_used":       correction_count,
        "attempts_remaining":  remaining,
        "hint": (
            "Please provide a description of a medical device issue, "
            "manufacturing defect, or quality complaint. "
            "Example: 'Crack found in pacemaker housing, batch #1234, reported in Texas, USA.'"
        ),
    }

    print(f"   Correction surfaced. Attempts: {correction_count}/{MAX_CORRECTION_ATTEMPTS}")

    return {
        "correction_response": correction_response,
        "node_log": [{"node": "request_correction_node",
                      "attempts_used":      correction_count,
                      "attempts_remaining": remaining,
                      "timestamp":          _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING — after input_validator
# ══════════════════════════════════════════════════════════════════════════════

def route_after_validation(state: RiskAnalysisState) -> str:
    if state.get("validation_passed"):
        # If the UI already provided structured fields, skip the LLM extraction
        # and go straight to the lightweight safety check node instead.
        if state.get("enriched_input"):
            return "enriched_context_node"
        return "context_node"
    if state.get("awaiting_correction"):
        return "request_correction_node"
    print(f"   🚫 Hard termination: {state.get('validation_category')}")
    return END


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — CONTEXT NODE
# Calls LLM. Extracts enriched fields from raw_input.
# Does NOT build per-agent payloads — that is payload_builder_node's job.
# ══════════════════════════════════════════════════════════════════════════════

def context_node(state: RiskAnalysisState) -> dict:
    print("\n[STEP 1] 🧠 Context Node: extracting context from input...")

    raw = state["raw_input"]
    llm = get_llm()

    response = llm.invoke(f"{EXTRACTION_PROMPT}\n\nClient Input: {raw}")

    try:
        clean  = response.content.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(clean)
    except Exception as exc:
        print(f"   ⚠ LLM parse failed ({exc}) — using fallback")
        parsed = {"urgency": False, "enriched": {"core_issue": raw}}

    urgency = parsed.get("urgency", False)
    e       = parsed.get("enriched", {})

    print(f"   Urgency : {urgency}")
    print(f"   Issue   : {e.get('core_issue', raw)}")
    print(f"   Enriched: {json.dumps(e, indent=2)}")

    complaint_id = e.get("complaint_id") or state.get("complaint_id") or "UNKNOWN"

    return {
        "urgency":      urgency,
        "extracted":    e,
        "complaint_id": complaint_id,
        "node_log":     [{"node": "context_node", "urgency": urgency,
                          "complaint_id": complaint_id, "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1b — ENRICHED CONTEXT NODE  (bypass path)
# Used when the UI provides structured complaint fields directly (enriched_input).
# Skips the full LLM extraction — only runs a lightweight safety check to
# determine `urgency` and `death_or_injury`, which cannot be reliably inferred
# from structured fields alone.
# Maps enriched_input fields → `extracted` dict (same shape as context_node output).
# ══════════════════════════════════════════════════════════════════════════════

def enriched_context_node(state: RiskAnalysisState) -> dict:
    print("\n[STEP 1b] ⚡ Enriched Context Node: using structured UI input (skipping LLM extraction)...")

    ei = state.get("enriched_input", {}) or {}

    # ── Lightweight LLM safety check ─────────────────────────────────────────
    # Only infer the two flags the UI cannot provide reliably.
    description = ei.get("core_issue") or state.get("raw_input", "")
    urgency        = False
    death_or_injury = False

    try:
        llm    = get_llm()
        resp   = llm.invoke(f"{SAFETY_CHECK_PROMPT}\n\nComplaint: {description}")
        clean  = resp.content.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(clean)
        urgency         = bool(parsed.get("urgency", False))
        death_or_injury = bool(parsed.get("death_or_injury", False))
    except Exception as exc:
        print(f"   ⚠ Safety check LLM error ({exc}) — defaulting to False")

    # ── Map enriched_input → extracted (same shape as context_node output) ────
    extracted = {
        "core_issue":           ei.get("core_issue")           or description,
        "complaint_id":         ei.get("complaint_id")         or state.get("complaint_id"),
        "product":              ei.get("product"),
        "product_type":         ei.get("product_type"),
        "date":                 ei.get("date"),
        "source":               ei.get("source"),
        "market_country":       ei.get("market_country"),
        "severity_hint":        ei.get("severity_hint"),
        "issue_type":           ei.get("issue_type"),
        "death_or_injury":      death_or_injury,          # from LLM
        "regulatory_standards": ei.get("regulatory_standards", []),
        "suspected_cause":      ei.get("suspected_cause"),
        "urgency_reason":       ei.get("urgency_reason"),
        "region":               ei.get("region"),
        "batch_number":         ei.get("batch_number"),
    }

    complaint_id = extracted.get("complaint_id") or state.get("complaint_id") or "UNKNOWN"

    print(f"   Urgency        : {urgency}")
    print(f"   Death/Injury   : {death_or_injury}")
    print(f"   Complaint ID   : {complaint_id}")
    print(f"   Source         : {extracted.get('source')}")
    print(f"   Severity hint  : {extracted.get('severity_hint')}")

    return {
        "urgency":      urgency,
        "extracted":    extracted,
        "complaint_id": complaint_id,
        "node_log": [{"node": "enriched_context_node", "mode": "structured_bypass",
                      "urgency": urgency, "death_or_injury": death_or_injury,
                      "complaint_id": complaint_id, "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — PAYLOAD BUILDER
# Reads extracted from state. Builds per-agent payloads.
# Adding a new agent = add its payload function in payloads.py only.
# ══════════════════════════════════════════════════════════════════════════════

def payload_builder_node(state: RiskAnalysisState) -> dict:
    print("\n[STEP 2] 📦 Payload Builder: building per-agent inputs...")

    e     = state.get("extracted", {})
    issue = e.get("core_issue", state["raw_input"])

    enriched_inputs = build_all_payloads(e, issue, state)

    print(f"   Built payloads for: {[k for k in enriched_inputs if k != '_meta']}")
    return {
        "enriched_inputs": enriched_inputs,
        "agent_results":   [],
        "node_log": [{"node": "payload_builder_node", "status": "complete",
                      "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING — dispatch_parallel
# Fires A5, A1, A2, A3 simultaneously via Send() API.
# Each receives only its own tailored payload.
# ══════════════════════════════════════════════════════════════════════════════

def dispatch_parallel(state: RiskAnalysisState) -> list[Send]:
    inputs = state["enriched_inputs"]
    tid    = state.get("thread_id", "unknown")
    print("\n[STEP 3] 📤 Dispatching parallel agents: A5, A1, A2, A3...")
    return [
        Send("A5_detection_agent",     {"agent_input": inputs["detection"],     "thread_id": tid}),
        Send("A1_similar_cases_agent", {"agent_input": inputs["similar_cases"], "thread_id": tid}),
        Send("A2_pattern_agent",       {"agent_input": inputs["pattern"],       "thread_id": tid}),
        Send("A3_severity_agent",      {"agent_input": inputs["severity"],      "thread_id": tid}),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# PARALLEL AGENTS — A5, A1, A2, A3
# Each wraps its sub-graph result with deep_serialize() before returning.
# No Command goto — routing handled by edges in build_orchestrator().
# ══════════════════════════════════════════════════════════════════════════════

def A5_detection_agent(state: dict) -> dict:
    print("   ▶ A5 Detection Agent running...")
    graph  = build_detection_graph()
    result = deep_serialize(graph.invoke(state["agent_input"]))
    score  = result.get("detection_score", 5)
    print(f"     Detection score : {score}")
    return {
        "agent_results": [{"agent": "A5", "type": "detection",
                           "score": score, "full": result}],
        "node_log": [{"node": "A5", "score": score, "timestamp": _now()}],
    }


def A1_similar_cases_agent(state: dict) -> dict:
    print("   ▶ A1 Similar Cases Agent running...")
    result       = deep_serialize(similar_cases_graph.invoke(state["agent_input"]))
    final_output = result.get("final_output") or {}

    count       = final_output.get("similarCount", 0)
    top_matches = final_output.get("topMatches",   [])

    # Compute avg_historical_rpn from actual match data (rpn or rpn_value field).
    # Falls back to None if the source documents don't carry an RPN field.
    rpn_values = [
        m.get("rpn") or m.get("rpn_value") or m.get("riskScore")
        for m in top_matches
        if m.get("rpn") or m.get("rpn_value") or m.get("riskScore")
    ]
    avg_historical_rpn = round(sum(rpn_values) / len(rpn_values)) if rpn_values else None

    print(f"     Similar cases found  : {count}")
    print(f"     Avg historical RPN   : {avg_historical_rpn if avg_historical_rpn is not None else 'N/A (no RPN in source)'}")
    return {
        "agent_results": [{"agent": "A1", "type": "similar_cases",
                           "full": {
                               "similar_cases":      top_matches,
                               "total_similar":      count,
                               "avg_historical_rpn": avg_historical_rpn,
                               "source":             "mongodb",
                           }}],
        "node_log": [{"node": "A1", "total_similar": count,
                      "avg_historical_rpn": avg_historical_rpn, "timestamp": _now()}],
    }


def A2_pattern_agent(state: dict) -> dict:
    print("   ▶ A2 Pattern Agent running...")
    graph  = build_pattern_graph()
    result = deep_serialize(graph.invoke(state["agent_input"]))

    trend_score    = result.get("trend_score", 5)
    trend_category = result.get("trend_category", "UNKNOWN")
    pattern        = result.get("identified_pattern", "No pattern identified")
    print(f"     Trend : {trend_score} | Pattern : {pattern}")
    return {
        "agent_results": [{"agent": "A2", "type": "pattern",
                           "trend_score":    trend_score,
                           "trend_category": trend_category,
                           "pattern":        pattern,
                           "full":           result}],
        "node_log": [{"node": "A2", "trend_score": trend_score,
                      "pattern": pattern, "timestamp": _now()}],
    }


def A3_severity_agent(state: dict) -> dict:
    print("   ▶ A3 Severity Agent running...")
    graph  = build_severity_graph()
    result = deep_serialize(graph.invoke(state["agent_input"]))

    score = result.get("severity_score", 5)
    label = result.get("severity_label", "MODERATE")
    print(f"     Severity : {score} ({label})")
    return {
        "agent_results": [{"agent": "A3", "type": "severity",
                           "score": score, "label": label, "full": result}],
        "node_log": [{"node": "A3", "score": score, "label": label,
                      "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# A4 — OCCURRENCE AGENT
# Natural fan-in — LangGraph waits for ALL 4 parallel agents to complete.
# Enriches occurrence input with A1 (similar cases) + A2 (pattern) context.
#
# SERIALIZATION — deep_serialize() handles the full nesting:
#
#   OccurrenceState
#     └── final_output: OccurrenceOutput        ← Pydantic model
#           ├── weighted_score: int
#           ├── rating: str
#           └── breakdown: OccurrenceScoreResponse  ← nested Pydantic model
#                 ├── scores: Dict[str, int]
#                 └── reasoning: str
#
#   deep_serialize() recurses into every level:
#     1. Hits OccurrenceOutput → model_dump(mode="json")
#        → returns {"weighted_score": 7, "rating": "HIGH",
#                   "breakdown": OccurrenceScoreResponse(...)}
#        → recurses into the returned dict
#     2. Hits OccurrenceScoreResponse at breakdown key
#        → model_dump(mode="json")
#        → returns {"scores": {...}, "reasoning": "..."}
#        → recurses into the returned dict
#     3. All primitives — returned unchanged
#   Final result: fully plain dict, no Pydantic objects anywhere.
# ══════════════════════════════════════════════════════════════════════════════

def A4_occurrence_agent(state: RiskAnalysisState) -> dict:
    print(f"\n[STEP 4] ▶ A4 Occurrence Agent running...")

    results = state.get("agent_results", [])

    # ── Extract structured outputs from A1 and A2 ─────────────────────────────
    pattern_full       = None
    similar_cases_full = None

    for r in results:
        t = r.get("type")
        if t == "pattern":
            pattern_full = r.get("full", {})
        elif t == "similar_cases":
            similar_cases_full = r.get("full", {})

    # ── Build pattern_data matching PatternData schema ────────────────────────
    pattern_data = None
    if pattern_full:
        pattern_data = {
            "complaint_id":          pattern_full.get("complaint_id",
                                         state["enriched_inputs"]["occurrence"]["input"]["complaint_id"]),
            "trend_score":           pattern_full.get("trend_score", 5),
            "trend_category":        pattern_full.get("trend_category", "UNKNOWN"),
            "confidence":            pattern_full.get("confidence", 0.0),
            "matched_complaint_ids": pattern_full.get("matched_complaint_ids", []),
            "identified_pattern":    pattern_full.get("identified_pattern",
                                         pattern_full.get("identified_pattern", "No pattern identified")),
            "explanation":           pattern_full.get("explanation", ""),
            "error":                 pattern_full.get("error"),
        }

    # ── Build similar_cases_data matching SimilarCasesData schema ─────────────
    similar_cases_data = None
    if similar_cases_full:
        raw_matches = similar_cases_full.get("similar_cases", [])

        # Normalize each match to SimilarCaseMatch schema
        # (A1 stores top_matches under "similar_cases" key)
        normalized_matches = []
        for m in raw_matches:
            normalized_matches.append({
                "recordId":          m.get("recordId", ""),
                "complaintId":       m.get("complaintId", m.get("complaint_id", "")),
                "dateReceived":      m.get("dateReceived", m.get("date_received", "")),
                "source":            m.get("source", ""),
                "regionCountry":     m.get("regionCountry", m.get("region_country")),
                "severity":          m.get("severity", ""),
                "productFamily":     m.get("productFamily", m.get("product_family", "")),
                "site":              m.get("site", ""),
                "descriptionOfIssue":m.get("descriptionOfIssue",
                                           m.get("description_of_issue",
                                           m.get("description", ""))),
                "status":            m.get("status", ""),
                "daysOpen":          m.get("daysOpen", m.get("days_open", 0)),
                "assignedTo":        m.get("assignedTo", m.get("assigned_to", "")),
                "isNc":              m.get("isNc", m.get("is_nc")),
                "ncId":              m.get("ncId", m.get("nc_id")),
                "fieldAction":       m.get("fieldAction", m.get("field_action")),
                "euReportable":      m.get("euReportable", m.get("eu_reportable")),
                "fdaReportable":     m.get("fdaReportable", m.get("fda_reportable")),
                "capaNeeded":        bool(m.get("capaNeeded", m.get("capa_needed", False))),
                "capaId":            m.get("capaId", m.get("capa_id")),
                "capaRationale":     m.get("capaRationale", m.get("capa_rationale", "")),
                "repeated":          bool(m.get("repeated", False)),
                "workflowStage":     m.get("workflowStage", m.get("workflow_stage", "")),
                "similarity":        float(m.get("similarity", 0.0)),
            })

        similar_cases_data = {
            "query":              similar_cases_full.get("query",
                                      state["enriched_inputs"]["occurrence"]["input"]["description"]),
            "similarityThreshold": similar_cases_full.get("similarity_threshold", 0.7),
            "similarCount":        similar_cases_full.get("total_similar", len(normalized_matches)),
            "message":             f"Found {len(normalized_matches)} similar case(s).",
            "topMatches":          normalized_matches,
        }

    # ── Build final occurrence input with all structured data ─────────────────
    occ_base  = state["enriched_inputs"]["occurrence"]
    occ_input = occ_base["input"]

    # Inject structured fields — these match ComplaintData exactly
    occ_input["pattern_data"]       = pattern_data
    occ_input["similar_cases_data"] = similar_cases_data

    # Keep legacy similar_cases populated as fallback
    occ_input["similar_cases"] = similar_cases_data["topMatches"] if similar_cases_data else []

    # Add plain-text additional_context as a human-readable summary
    avg_rpn   = similar_cases_full.get("avg_historical_rpn", "N/A") if similar_cases_full else "N/A"
    trend_s   = pattern_full.get("trend_score", "N/A")              if pattern_full       else "N/A"
    pattern_s = pattern_full.get("identified_pattern", "N/A")       if pattern_full       else "N/A"
    occ_input["additional_context"] = (
        f"Similar cases avg RPN: {avg_rpn}. "
        f"Pattern: {pattern_s}. "
        f"Trend score: {trend_s}."
    )

    print(f"   pattern_data       : {'✓' if pattern_data       else '✗ not available'}")
    print(f"   similar_cases_data : {'✓ ' + str(similar_cases_data['similarCount']) + ' cases' if similar_cases_data else '✗ not available'}")

    # ── Invoke + deep serialize ───────────────────────────────────────────────
    occurrence_result = deep_serialize(occurrence_graph.invoke(occ_base))

    final      = occurrence_result.get("final_output") or {}
    occ_score  = final.get("weighted_score", 5)
    occ_rating = final.get("rating", "MODERATE")
    breakdown  = final.get("breakdown") or {}

    print(f"   Occurrence score   : {occ_score} ({occ_rating})")
    print(f"   Breakdown scores   : {breakdown.get('scores', {})}")

    return {
        "occurrence_score": occ_score,
        "agent_results": [{"agent": "A4", "type": "occurrence",
                           "score":     occ_score,
                           "rating":    occ_rating,
                           "breakdown": breakdown,
                           "full":      occurrence_result}],
        "node_log": [{"node": "A4", "score": occ_score, "rating": occ_rating,
                      "timestamp": _now()}],
    }

# ══════════════════════════════════════════════════════════════════════════════
# RPN CALCULATOR
# Runs sequentially after A4.
# Computes RPN = Severity × Occurrence × Detection.
# Uses safe defaults (5) for any score that is None or missing.
# ══════════════════════════════════════════════════════════════════════════════

def rpn_calculator_node(state: RiskAnalysisState) -> dict:
    print(f"\n[STEP 4.5] ▶ RPN Calculator Node...")

    results = state.get("agent_results", [])
    scores  = {}
    for r in results:
        t = r.get("type")
        if t == "detection":
            scores["detection"]  = r.get("score")
        elif t == "severity":
            scores["severity"]   = r.get("score")
            scores["label"]      = r.get("label", "MODERATE")
        elif t == "occurrence":
            scores["occurrence"] = r.get("score")

    # Safe defaults — never multiply None
    S   = scores.get("severity")  or 5
    D   = scores.get("detection") or 5
    O   = scores.get("occurrence") or 5
    rpn = round(S * O * D, 2)

    if   rpn >= 600: rpn_level = "CRITICAL"
    elif rpn >= 300: rpn_level = "HIGH"
    elif rpn >= 100: rpn_level = "MEDIUM"
    else:            rpn_level = "LOW"

    print(f"   RPN = {S} (S) × {O} (O) × {D} (D) = {rpn} → {rpn_level}")
    return {
        "severity_score":   S,
        "severity_label":   scores.get("label", "MODERATE"),
        "detection_score":  D,
        "occurrence_score": O,
        "rpn_value":        rpn,
        "rpn_level":        rpn_level,
        "node_log": [{"node": "rpn_calculator_node", "rpn": rpn,
                      "rpn_level": rpn_level, "S": S, "O": O, "D": D,
                      "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# A6 — REGULATORY AGENT
# Injects live RPN scores on top of enriched regulatory payload.
# deep_serialize() at invoke.
# ══════════════════════════════════════════════════════════════════════════════

def A6_regulatory_agent(state: RiskAnalysisState) -> dict:
    print("\n[STEP 5] ▶ A6 Regulatory Agent: evaluating compliance...")
    graph = build_regulatory_graph()

    reg_input = {
        **state["enriched_inputs"]["regulatory"],
        "severity_score":   state.get("severity_score"),
        "occurrence_score": state.get("occurrence_score"),
        "detection_score":  state.get("detection_score"),
        "risk_score":       int(state.get("rpn_value") or 0),
        "severity":         state.get("severity_label"),
    }

    result     = deep_serialize(graph.invoke(reg_input))
    reportable = result.get("reportable", False)
    risk_level = result.get("compliance_risk_level", "unknown")
    print(f"   Reportable : {reportable} | Risk level : {risk_level}")

    return {
        "regulatory_output": result,
        "node_log": [{"node": "A6", "reportable": reportable,
                      "risk_level": risk_level, "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# A7 — AI REASONING AGENT
# Synthesizes full justification from all previous results.
# deep_serialize() at invoke.
# ══════════════════════════════════════════════════════════════════════════════

def A7_reasoning_agent(state: RiskAnalysisState) -> dict:
    print("\n[STEP 6] ▶ A7 AI Reasoning Agent: synthesizing justification...")

    pattern_result = next(
        (r for r in state.get("agent_results", []) if r.get("type") == "pattern"), {}
    )
    reg  = state.get("regulatory_output", {}) or {}
    meta = state["enriched_inputs"]["_meta"]

    reasoning_input = {
        "input": {
            "complaint_id":       state["enriched_inputs"]["regulatory"].get("complaint_id", "UNKNOWN"),
            "risk_score":         min(int(state.get("rpn_value") or 1), 100),
            "pattern":            pattern_result.get("pattern", "No pattern identified"),
            "severity_level":     state.get("severity_label", "MODERATE"),
            "nc_source":          meta.get("issue", "Unknown"),
            "regulatory_impact":  reg.get("justification",
                                          reg.get("regulatory_classification", "Not assessed")),
            "customer_impact":    f"Severity: {state.get('severity_label')} | RPN: {state.get('rpn_value')}",
            "additional_context": (
                f"RPN Level: {state.get('rpn_level')}. "
                f"Reportable: {reg.get('reportable')}. "
                f"Urgency: {meta.get('urgency')}."
            ),
            "additional_data": {
                "severity_score":   state.get("severity_score"),
                "occurrence_score": state.get("occurrence_score"),
                "detection_score":  state.get("detection_score"),
                "rpn_value":        state.get("rpn_value"),
                "rpn_level":        state.get("rpn_level"),
                "report_type":      reg.get("report_type"),
                "timeline_days":    reg.get("reporting_timeline_days"),
            },
        },
        "iteration": 0,
    }

    result     = deep_serialize(aireasoning_graph.invoke(reasoning_input))
    final      = result.get("final_output", {}) or {}
    confidence = final.get("confidence_level", "N/A") if isinstance(final, dict) else "N/A"
    print(f"   Confidence : {confidence}")

    return {
        "reasoning_output": result,
        "node_log": [{"node": "A7", "confidence": confidence, "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# FINALIZE NODE
# Assembles all state fields into one clean final report.
# All sub-graph results already deep_serialized — safe to read directly.
# ══════════════════════════════════════════════════════════════════════════════

def finalize_node(state: RiskAnalysisState) -> dict:
    print("\n✅ Risk Analysis complete — building final report...")

    reg    = state.get("regulatory_output", {}) or {}
    reason = state.get("reasoning_output",  {}) or {}

    # deep_serialize already ran — final_output is a plain dict
    final_reason = reason.get("final_output", {}) or {}

    # ── Build per-agent summary from agent_results ────────────────────────────
    agent_results = state.get("agent_results", [])
    agent_summary = {}

    for r in agent_results:
        t = r.get("type")

        if t == "similar_cases":
            full = r.get("full", {})
            agent_summary["similar_cases"] = {
                "total_similar":      full.get("total_similar", 0),
                "avg_historical_rpn": full.get("avg_historical_rpn"),
                "source":             full.get("source"),
                "top_matches":        full.get("similar_cases", []),
            }

        elif t == "pattern":
            agent_summary["pattern"] = {
                "trend_score":    r.get("trend_score"),
                "trend_category": r.get("trend_category"),
                "pattern":        r.get("pattern"),
            }

        elif t == "detection":
            full = r.get("full", {})
            agent_summary["detection"] = {
                "score":          r.get("score"),
                "confidence":     full.get("confidence"),
                "rule_reference": full.get("rule_reference"),
                "explanation":    full.get("explanation"),
            }

        elif t == "severity":
            agent_summary["severity"] = {
                "score": r.get("score"),
                "label": r.get("label"),
            }

        elif t == "occurrence":
            # final_output + breakdown already plain dicts — deep_serialized in A4
            final_occ = r.get("full", {}).get("final_output", {}) or {}
            agent_summary["occurrence"] = {
                "score":     r.get("score"),
                "rating":    r.get("rating"),
                "breakdown": r.get("breakdown", {}),
                # breakdown.scores contains per-parameter scores e.g.
                # {"HF": 8, "TR": 9, "PS": 7, ...}
            }

    report = {
        "status": "complete",
        "rpn": {
            "severity_score":   state.get("severity_score"),
            "severity_label":   state.get("severity_label"),
            "occurrence_score": state.get("occurrence_score"),
            "detection_score":  state.get("detection_score"),
            "rpn_value":        state.get("rpn_value"),
            "rpn_level":        state.get("rpn_level"),
        },
        "agent_summaries": agent_summary,
        "regulatory": {
            "reportable":                reg.get("reportable"),
            "regulatory_classification": reg.get("regulatory_classification"),
            "report_type":               reg.get("report_type"),
            "reporting_timeline_days":   reg.get("reporting_timeline_days"),
            "compliance_risk_level":     reg.get("compliance_risk_level"),
            "authority":                 reg.get("authority"),
            "justification":             reg.get("justification"),
        },
        "reasoning": {
            "reasoning":        final_reason.get("reasoning"),
            "key_factors":      final_reason.get("key_factors", []),
            "recommendations":  final_reason.get("recommendations", []),
            "confidence_level": final_reason.get("confidence_level"),
        },
    }

    print(f"   Final report assembled. RPN: {state.get('rpn_value')} ({state.get('rpn_level')})")
    return {
        "final_report": report,
        "node_log": [{"node": "finalize_node", "status": "complete",
                      "rpn_level": state.get("rpn_level"),
                      "timestamp": _now()}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# BUILD GRAPH
# All routing lives here — not inside node functions.
# Full flow visible in one place.
# ══════════════════════════════════════════════════════════════════════════════

def _tracked(node_name: str, fn):
    """
    Wraps a node function so it writes running/done/error status to Redis
    and publishes to the agent_events Pub/Sub channel on each state change.
    Zero changes required to the individual node functions.
    """
    from config.redis_config import _NODE_LABELS, _NODE_AGENT_IDS
    label    = _NODE_LABELS.get(node_name, node_name)
    agent_id = _NODE_AGENT_IDS.get(node_name)

    def wrapper(state):
        tid = state.get("thread_id", "unknown") if isinstance(state, dict) else "unknown"
        write_agent_status(tid, node_name, "running")
        publish_agent_event(tid, {"type": "node_start", "node": node_name,
                                  "label": label, "agent_id": agent_id, "ts": _now()})
        try:
            result = fn(state)
            write_agent_status(tid, node_name, "done")
            end_event = {"type": "node_end", "node": node_name,
                         "label": label, "agent_id": agent_id, "ts": _now()}
            # Attach live RPN scores when calculator finishes
            if node_name == "rpn_calculator_node" and isinstance(result, dict):
                end_event["rpn_update"] = {
                    "severity":   result.get("severity_score"),
                    "occurrence": result.get("occurrence_score"),
                    "detection":  result.get("detection_score"),
                    "rpn":        result.get("rpn_value"),
                }
            publish_agent_event(tid, end_event)
            return result
        except Exception as exc:
            write_agent_status(tid, node_name, "error")
            publish_agent_event(tid, {"type": "node_error", "node": node_name,
                                      "label": label, "agent_id": agent_id,
                                      "error": str(exc), "ts": _now()})
            raise
    return wrapper


def build_orchestrator():
    """
    Assembles the full O2 Risk Analysis Orchestrator graph.

    Topology:
        START
          └─► input_validator
                ├─► (malicious/terminated) ─► END
                ├─► (awaiting_correction)  ─► request_correction_node ─► END
                └─► (valid)                ─► context_node
                                                └─► payload_builder_node
                                                      └─► [A5|A1|A2|A3]  fan-out
                                                            └─► A4_occurrence_agent  fan-in
                                                                  └─► rpn_calculator_node
                                                                        └─► A6_regulatory_agent
                                                                              └─► A7_reasoning_agent
                                                                                    └─► finalize_node
                                                                                          └─► END
    """
    g = StateGraph(RiskAnalysisState)

    # ── Register nodes (all wrapped with status tracker) ─────────────────────
    t = _tracked  # shorthand
    g.add_node("input_validator",         t("input_validator",         input_validator))
    g.add_node("request_correction_node", t("request_correction_node", request_correction_node))
    g.add_node("context_node",            t("context_node",            context_node))
    g.add_node("enriched_context_node",   t("enriched_context_node",   enriched_context_node))
    g.add_node("payload_builder_node",    t("payload_builder_node",    payload_builder_node))
    g.add_node("A5_detection_agent",      t("A5_detection_agent",      A5_detection_agent))
    g.add_node("A1_similar_cases_agent",  t("A1_similar_cases_agent",  A1_similar_cases_agent))
    g.add_node("A2_pattern_agent",        t("A2_pattern_agent",        A2_pattern_agent))
    g.add_node("A3_severity_agent",       t("A3_severity_agent",       A3_severity_agent))
    g.add_node("A4_occurrence_agent",     t("A4_occurrence_agent",     A4_occurrence_agent))
    g.add_node("rpn_calculator_node",     t("rpn_calculator_node",     rpn_calculator_node))
    g.add_node("A6_regulatory_agent",     t("A6_regulatory_agent",     A6_regulatory_agent))
    g.add_node("A7_reasoning_agent",      t("A7_reasoning_agent",      A7_reasoning_agent))
    g.add_node("finalize_node",           t("finalize_node",           finalize_node))

    # ── Entry ─────────────────────────────────────────────────────────────────
    g.add_edge(START, "input_validator")

    # ── Validation gate ───────────────────────────────────────────────────────
    g.add_conditional_edges(
        "input_validator",
        route_after_validation,
        {
            "context_node":            "context_node",
            "enriched_context_node":   "enriched_context_node",
            "request_correction_node": "request_correction_node",
            END:                       END,
        }
    )

    # ── Correction node → END ─────────────────────────────────────────────────
    g.add_edge("request_correction_node", END)

    # ── Both context paths converge on payload_builder_node ──────────────────
    g.add_edge("context_node",          "payload_builder_node")
    g.add_edge("enriched_context_node", "payload_builder_node")

    # ── Fan-out: payload builder → A5, A1, A2, A3 in parallel ────────────────
    g.add_conditional_edges(
        "payload_builder_node",
        dispatch_parallel,
        [
            "A1_similar_cases_agent",
            "A2_pattern_agent",
            "A3_severity_agent",
            "A5_detection_agent",
        ]
    )

    # ── Fan-in: all 4 parallel agents → A4 ────────────────────────────────────
    # LangGraph natural fan-in: A4 runs ONCE after ALL 4 complete.
    g.add_edge("A1_similar_cases_agent", "A4_occurrence_agent")
    g.add_edge("A2_pattern_agent",       "A4_occurrence_agent")
    g.add_edge("A3_severity_agent",      "A4_occurrence_agent")
    g.add_edge("A5_detection_agent",     "A4_occurrence_agent")

    # ── Sequential: A4 → RPN → A6 → A7 → finalize → END ─────────────────────
    g.add_edge("A4_occurrence_agent",  "rpn_calculator_node")
    g.add_edge("rpn_calculator_node",  "A6_regulatory_agent")
    g.add_edge("A6_regulatory_agent",  "A7_reasoning_agent")
    g.add_edge("A7_reasoning_agent",   "finalize_node")
    g.add_edge("finalize_node",        END)

    # ── Compile with sync Redis checkpointing ─────────────────────────────────
    # RedisSaver (sync) works at module-level import time — no event loop needed.
    # Uses centralised redis_client from config (reads REDIS_URL from .env).
    from langgraph.checkpoint.redis import RedisSaver
    checkpointer = RedisSaver(redis_client=redis_client)
    checkpointer.setup()
    return g.compile(checkpointer=checkpointer)


# ── Module-level graph instance ───────────────────────────────────────────────
# Import in router.py:
#   from .orchestrator import orchestrator_graph, redis_client, MAX_CORRECTION_ATTEMPTS
#
# Invoke with thread_id for checkpointing:
#   config = {"configurable": {"thread_id": "capa-abc123"}}
#   result = orchestrator_graph.invoke({"raw_input": "..."}, config=config)
orchestrator_graph = build_orchestrator()