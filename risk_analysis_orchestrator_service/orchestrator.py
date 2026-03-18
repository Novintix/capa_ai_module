"""
orchestrator_service/orchestrator.py

Risk Analysis Orchestrator (O2) — IMPROVED VERSION

Changes from original:
  1. Natural LangGraph fan-in  — A4 guard removed, edges do the waiting
  2. Edges in build_orchestrator() — Command goto removed from nodes
  3. Intent node split — intent_node + payload_builder_node
  4. input_validator added — guards before any LLM call
  5. Redis checkpointing — crash recovery on every node
  6. All routing visible in one place — build_orchestrator()

Flow:
    START
      ↓
    input_validator        ← guards empty / invalid input
      ↓
    intent_node            ← LLM extracts context only
      ↓
    payload_builder_node   ← builds per-agent payloads
      ↓
    dispatch_parallel()    ← Send() fan-out to 4 agents
      ├── A5 Detection Agent
      ├── A1 Similar Cases Agent
      ├── A2 Pattern Agent
      └── A3 Severity Agent
      ↓  (natural fan-in — LangGraph waits for ALL 4)
    A4 Occurrence Agent    ← runs ONCE after all 4 done
      ↓
    A6 Regulatory Agent
      ↓
    A7 AI Reasoning Agent
      ↓
    finalize_node
      ↓
    END
"""

import json
import operator
from datetime import datetime
from typing import Annotated, Optional
from typing_extensions import TypedDict

import redis
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command
from langgraph.checkpoint.redis import RedisSaver

from Agents.detection.graph   import create_detection_graph as build_detection_graph
from Agents.pattern.graph     import create_pattern_graph   as build_pattern_graph
from Agents.severity.graph    import build_graph            as build_severity_graph
from Agents.occurrence.graph  import occurrence_graph
from Agents.regulatory.graph  import create_regulatory_graph as build_regulatory_graph
from Agents.aireasoning.graph import aireasoning_graph
from Agents.similar_cases.graph import similar_cases_graph

from config.aws_bedrock_config import get_llm
from .prompts import EXTRACTION_PROMPT
from .payloads import build_all_payloads


# ══════════════════════════════════════════════════════════════════════════════
# REDIS CLIENT
# ══════════════════════════════════════════════════════════════════════════════

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=False,
)


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

from risk_analysis_orchestrator_service.state import RiskAnalysisState


# ══════════════════════════════════════════════════════════════════════════════
# NODE 0 — INPUT VALIDATOR
# Guards before any LLM call.
# Halts immediately on invalid input.
# ══════════════════════════════════════════════════════════════════════════════

def input_validator(state: RiskAnalysisState) -> dict:
    """
    Validates raw_input before any LLM call.
    Returns error state and routes to END if invalid.
    Routing handled by conditional edge in build_orchestrator().
    """
    print("\n[STEP 0] 🔍 Input Validator: checking input...")

    raw = state.get("raw_input", "")

    # Check 1 — must exist and not be empty
    if not raw or not raw.strip():
        print("   ✗ Validation failed: empty input")
        return {
            "validation_passed": False,
            "validation_error":  "raw_input is empty or missing",
            "node_log": [{"node": "input_validator", "status": "failed", "reason": "empty input"}],
        }

    # Check 2 — minimum length (avoid single-word inputs)
    if len(raw.strip()) < 10:
        print("   ✗ Validation failed: input too short")
        return {
            "validation_passed": False,
            "validation_error":  "raw_input too short — minimum 10 characters",
            "node_log": [{"node": "input_validator", "status": "failed", "reason": "too short"}],
        }

    print("   ✓ Validation passed")
    return {
        "validation_passed": True,
        "node_log": [{"node": "input_validator", "status": "passed", "timestamp": str(datetime.now())}],
    }


def route_after_validation(state: RiskAnalysisState) -> str:
    """
    Conditional edge after input_validator.
    Pass  → intent_node
    Fail  → END
    """
    if state.get("validation_passed"):
        return "context_node"
    return END


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — INTENT NODE
# Responsibility: call LLM, extract fields only.
# Does NOT build agent payloads — that is payload_builder_node's job.
# ══════════════════════════════════════════════════════════════════════════════
def context_node(state: RiskAnalysisState) -> dict:
    """
    Calls LLM. Extracts enriched fields.
    Does NOT build per-agent payloads.
    Returns extracted dict to state — payload_builder reads it next.
    """
    print("\n[STEP 1] 🧠 Context Node: extracting context from input...")

    raw = state["raw_input"]
    llm = get_llm()

    response = llm.invoke(f"{EXTRACTION_PROMPT}\n\nClient Input: {raw}")

    try:
        clean  = (response.content.strip()
                  .replace("```json", "")
                  .replace("```", ""))
        parsed = json.loads(clean)
    except Exception as exc:
        print(f"   ⚠ LLM parse failed ({exc}) — using fallback")
        parsed = {
            "urgency":  False,
            "enriched": {"core_issue": raw},
        }

    urgency = parsed.get("urgency", False)
    e       = parsed.get("enriched", {})

    print(f"   Urgency : {urgency}")
    print(f"   Issue   : {e.get('core_issue', raw)}")
    print(f"   Enriched: {json.dumps(e, indent=2)}")

    return {
        "urgency":   urgency,
        "extracted": e,                          # raw extraction — payload_builder reads this
        "node_log":  [{"node": "context_node",
                       "urgency": urgency,
                       "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — PAYLOAD BUILDER
# Responsibility: build per-agent payloads only.
# Reads extracted from state. Builds enriched_inputs.
# Separated from intent_node so each has one responsibility.
# ══════════════════════════════════════════════════════════════════════════════

def payload_builder_node(state: RiskAnalysisState) -> dict:
    """
    Reads LLM extraction from state.
    Delegates payload construction to risk_analysis_orchestrator_service/payloads.py.
    Adding a new agent = add its payload function in payloads.py only.
    """
    print("\n[STEP 2] 📦 Payload Builder: building per-agent inputs...")

    e     = state.get("extracted", {})
    issue = e.get("core_issue", state["raw_input"])

    enriched_inputs = build_all_payloads(e, issue, state)

    print(f"   Built payloads for: {[k for k in enriched_inputs if k != '_meta']}")
    print("   ✓ Payloads created successfully")
    return {
        "enriched_inputs": enriched_inputs,
        "agent_results":   [],              # initialise before parallel agents write
        "node_log": [{"node": "payload_builder_node", "status": "complete", "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTION — dispatch_parallel
# Reads enriched_inputs. Returns Send objects for parallel dispatch.
# ══════════════════════════════════════════════════════════════════════════════

def dispatch_parallel(state: RiskAnalysisState) -> list[Send]:
    """
    Conditional edge after payload_builder_node.
    Fires A5, A1, A2, A3 simultaneously using Send API.
    Each receives only its own tailored payload.
    """
    inputs = state["enriched_inputs"]
    print("\n[STEP 3] 📤 Dispatching parallel agents: A5, A1, A2, A3...")

    return [
        Send("A5_detection_agent",     {"agent_input": inputs["detection"]}),
        Send("A1_similar_cases_agent", {"agent_input": inputs["similar_cases"]}),
        Send("A2_pattern_agent",       {"agent_input": inputs["pattern"]}),
        Send("A3_severity_agent",      {"agent_input": inputs["severity"]}),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# PARALLEL AGENTS — A5, A1, A2, A3
# Each returns dict only — no Command goto.
# Routing is handled by explicit edges in build_orchestrator().
# ══════════════════════════════════════════════════════════════════════════════

def A5_detection_agent(state: dict) -> dict:
    """
    Runs detection sub-graph.
    Returns detection score appended to agent_results.
    No goto — edge in build_orchestrator() routes to A4.
    """
    print("   ▶ A5 Detection Agent running...")
    graph  = build_detection_graph()
    result = graph.invoke(state["agent_input"])
    score  = result.get("detection_score", 5)
    print(f"     Detection score : {score}")

    return {
        "agent_results": [{"agent": "A5",
                           "type":  "detection",
                           "score": score,
                           "full":  result}],
        "node_log": [{"node": "A5", "score": score, "timestamp": str(datetime.now())}],
    }


def A1_similar_cases_agent(state: dict) -> dict:
    """
    Runs similar cases sub-graph.
    Returns similar cases list to agent_results.
    No goto — edge in build_orchestrator() routes to A4.
    """
    print("   ▶ A1 Similar Cases Agent running...")
    
    result = similar_cases_graph.invoke(state["agent_input"])
    
    # Extract results using Pydantic or dict access
    final_output = result.get("final_output")
    if hasattr(final_output, "model_dump"):
        final_output = final_output.model_dump()
    elif hasattr(final_output, "dict"):
        final_output = final_output.dict()
        
    count = final_output.get("similarCount", 0) if final_output else 0
    top_matches = final_output.get("topMatches", []) if final_output else []
    
    # Calculate avg RPN for A4 logic
    total_rpn = 0
    valid_rpns = 0
    for m in top_matches:
        similarity = m.get("similarity", 0)
        # Mocking RPN because MongoDB fields might not mapped exactly to RPN yet
        # But we can look at severity/occurrence if they exist in metadata
        pass

    avg_historical_rpn = 250 # Fallback for now

    print(f"     Similar cases found: {count}")

    return {
        "agent_results": [{"agent": "A1",
                           "type":  "similar_cases",
                           "full":  {
                               "similar_cases": top_matches,
                               "total_similar": count,
                               "avg_historical_rpn": avg_historical_rpn,
                               "source": "mongodb"
                           }}],
        "node_log": [{"node": "A1", "source": "mongodb", "total_similar": count, "timestamp": str(datetime.now())}],
    }


def A2_pattern_agent(state: dict) -> dict:
    """
    Runs pattern sub-graph.
    Returns trend score and pattern appended to agent_results.
    No goto — edge in build_orchestrator() routes to A4.
    """
    print("   ▶ A2 Pattern Agent running...")
    graph  = build_pattern_graph()
    result = graph.invoke(state["agent_input"])

    trend_score    = result.get("trend_score", 5)
    trend_category = result.get("trend_category", "UNKNOWN")
    pattern        = result.get("identified_pattern", "No pattern identified")
    print(f"     Trend : {trend_score} | Pattern : {pattern}")

    return {
        "agent_results": [{"agent":          "A2",
                           "type":           "pattern",
                           "trend_score":    trend_score,
                           "trend_category": trend_category,
                           "pattern":        pattern,
                           "full":           result}],
        "node_log": [{"node": "A2", "trend_score": trend_score, "pattern": pattern, "timestamp": str(datetime.now())}],
    }


def A3_severity_agent(state: dict) -> dict:
    """
    Runs severity sub-graph.
    Returns severity score appended to agent_results.
    No goto — edge in build_orchestrator() routes to A4.
    """
    print("   ▶ A3 Severity Agent running...")
    graph  = build_severity_graph()
    result = graph.invoke(state["agent_input"])

    score = result.get("severity_score", 5)
    label = result.get("severity_label", "MODERATE")
    print(f"     Severity : {score} ({label})")

    return {
        "agent_results": [{"agent": "A3",
                           "type":  "severity",
                           "score": score,
                           "label": label,
                           "full":  result}],
        "node_log": [{"node": "A3", "score": score, "label": label, "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# A4 — OCCURRENCE AGENT
# Natural fan-in — LangGraph edges ensure this runs ONCE
# after ALL 4 parallel agents complete.
# No guard needed. No wasted calls.
# ══════════════════════════════════════════════════════════════════════════════

def A4_occurrence_agent(state: RiskAnalysisState) -> dict:
    """
    Runs ONCE after A1 and A2 complete.
    LangGraph fan-in via edges handles the waiting.

    Enriches occurrence input with similar cases and trend context.
    Returns occurrence score to state.
    """
    print(f"\n[STEP 4] ▶ A4 Occurrence Agent: A1 and A2 results received...")

    results = state.get("agent_results", [])

    # Extract scores from A1 and A2 results
    scores = {}
    for r in results:
        t = r.get("type")
        if t == "pattern":
            scores["trend"]              = r.get("trend_score", 5)
            scores["pattern"]            = r.get("pattern", "")
        elif t == "similar_cases":
            scores["avg_historical_rpn"] = (r.get("full", {})
                                             .get("avg_historical_rpn", 0))

    # Enrich occurrence input with parallel context
    occ_base = state["enriched_inputs"]["occurrence"]
    occ_base["input"]["additional_context"] = (
        f"Similar cases avg RPN: {scores.get('avg_historical_rpn', 'N/A')}. "
        f"Pattern: {scores.get('pattern', 'N/A')}. "
        f"Trend score: {scores.get('trend', 'N/A')}."
    )

    # Run occurrence sub-graph
    occurrence_result = occurrence_graph.invoke(occ_base)

    final     = occurrence_result.get("final_output", {})
    occ_score = (final.get("weighted_score", 5)
                 if isinstance(final, dict)
                 else getattr(final, "weighted_score", 5))
    occ_rating = (final.get("rating", "MODERATE")
                  if isinstance(final, dict)
                  else getattr(final, "rating", "MODERATE"))

    print(f"   Occurrence score : {occ_score} ({occ_rating})")

    return {
        "occurrence_score": occ_score,
        "agent_results": [{"agent":  "A4",
                           "type":   "occurrence",
                           "score":  occ_score,
                           "rating": occ_rating,
                           "full":   occurrence_result}],
        "node_log": [{"node": "A4", "O": occ_score, "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# RPN CALCULATOR NODE
# Natural fan-in from A3, A4, and A5
# ══════════════════════════════════════════════════════════════════════════════

def rpn_calculator_node(state: RiskAnalysisState) -> dict:
    """
    Runs ONCE after A3, A4, and A5 complete.
    Computes final RPN = Severity x Occurrence x Detection.
    Returns scores to state — A6 reads them via edges.
    """
    print(f"\n[STEP 4.5] ▶ RPN Calculator Node: A3, A4, A5 completed...")

    results = state.get("agent_results", [])

    # Extract scores from results
    scores = {}
    for r in results:
        t = r.get("type")
        if t == "detection":
            scores["detection"] = r.get("score")
        elif t == "severity":
            scores["severity"] = r.get("score")
            scores["label"]    = r.get("label", "MODERATE")
        elif t == "occurrence":
            scores["occurrence"] = r.get("score")

    # RPN = Severity × Occurrence × Detection
    S   = scores.get("severity")
    D   = scores.get("detection")
    O   = scores.get("occurrence")
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
        "rpn_value":        rpn,
        "rpn_level":        rpn_level,
        "node_log": [{"node": "rpn_calculator_node", "rpn": rpn,
                      "rpn_level": rpn_level, "S": S, "O": O, "D": D, 
                      "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# A6 — REGULATORY AGENT
# No Command goto — edge in build_orchestrator() routes to A7.
# ══════════════════════════════════════════════════════════════════════════════

def A6_regulatory_agent(state: RiskAnalysisState) -> dict:
    """
    Checks regulatory compliance using RPN scores from A4.
    Returns regulatory_output to state.
    No goto — edge routes to A7.
    """
    print("\n[STEP 5] ▶ A6 Regulatory Agent: evaluating compliance...")
    graph = build_regulatory_graph()

    # Inject live RPN scores on top of enriched regulatory payload
    reg_input = {
        **state["enriched_inputs"]["regulatory"],
        "severity_score":   state.get("severity_score"),
        "occurrence_score": state.get("occurrence_score"),
        "detection_score":  state.get("detection_score"),
        "risk_score":       int(state.get("rpn_value", 0)),
        "severity":         state.get("severity_label"),
    }

    result     = graph.invoke(reg_input)
    reportable = result.get("reportable", False)
    risk_level = result.get("compliance_risk_level", "unknown")
    print(f"   Reportable : {reportable} | Compliance risk : {risk_level}")

    return {
        "regulatory_output": result,
        "node_log": [{"node": "A6",
                      "reportable": reportable,
                      "risk_level": risk_level,
                      "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# A7 — AI REASONING AGENT
# No Command goto — edge in build_orchestrator() routes to finalize.
# ══════════════════════════════════════════════════════════════════════════════

def A7_reasoning_agent(state: RiskAnalysisState) -> dict:
    """
    Synthesizes full justification from all previous results.
    Returns reasoning_output to state.
    No goto — edge routes to finalize_node.
    """
    print("\n[STEP 6] ▶ A7 AI Reasoning Agent: synthesizing justification...")

    pattern_result = next(
        (r for r in state.get("agent_results", []) if r.get("type") == "pattern"),
        {}
    )
    reg  = state.get("regulatory_output", {}) or {}
    meta = state["enriched_inputs"]["_meta"]

    reasoning_input = {
        "input": {
            "complaint_id":       state["enriched_inputs"]["regulatory"].get("complaint_id", "UNKNOWN"),
            "risk_score":         min(int(state.get("rpn_value", 1)), 100),  # clamped to schema max
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

    result = aireasoning_graph.invoke(reasoning_input)

    final      = result.get("final_output", {})
    confidence = (final.get("confidence_level")
                  if isinstance(final, dict)
                  else getattr(final, "confidence_level", "N/A"))
    print(f"   Confidence : {confidence}")

    return {
        "reasoning_output": result,
        "node_log": [{"node": "A7", "confidence": confidence, "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# FINALIZE NODE
# ══════════════════════════════════════════════════════════════════════════════

def finalize_node(state: RiskAnalysisState) -> dict:
    """
    Assembles all state fields into one clean final report.
    Handles None and Pydantic model outputs safely.
    """
    print("\n✅ Risk Analysis complete — building final report...")

    reg    = state.get("regulatory_output", {}) or {}
    reason = state.get("reasoning_output",  {}) or {}

    # Handle both plain dict and Pydantic model from A7
    final_reason = reason.get("final_output", {})
    if not isinstance(final_reason, dict):
        final_reason = (final_reason.dict()
                        if hasattr(final_reason, "dict")
                        else {})

    # ── Extract per-agent summaries from agent_results ──────────────────────
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
            agent_summary["detection"] = {
                "score":           r.get("score"),
                "confidence":      r.get("full", {}).get("confidence"),
                "rule_reference":  r.get("full", {}).get("rule_reference"),
                "explanation":     r.get("full", {}).get("explanation"),
            }
        elif t == "severity":
            agent_summary["severity"] = {
                "score": r.get("score"),
                "label": r.get("label"),
            }
        elif t == "occurrence":
            full = r.get("full", {}).get("final_output", {})
            if hasattr(full, "dict"):
                full = full.dict()
            agent_summary["occurrence"] = {
                "score":  r.get("score"),
                "rating": r.get("rating"),
            }

    report = {
        "status":  "complete",
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

    print("   Final report assembled.")

    return {
        "final_report": report,
        "node_log": [{"node": "finalize_node", "status": "complete",
                      "rpn_level": state.get("rpn_level"),
                      "timestamp": str(datetime.now())}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# BUILD GRAPH
# All routing lives here — not inside node functions.
# Full flow visible in one place.
# ══════════════════════════════════════════════════════════════════════════════

def build_orchestrator():
    """
    Assembles the full O2 Risk Analysis Orchestrator graph.

    Topology:
        START
          └─► input_validator
                ├─► (invalid) ─► END
                └─► (valid)   ─► context_node
                                    └─► payload_builder_node
                                          └─► [A5|A1|A2|A3]  parallel fan-out
                                                └─► A4_occurrence_agent  fan-in
                                                      └─► A6_regulatory_agent
                                                            └─► A7_reasoning_agent
                                                                  └─► finalize_node
                                                                        └─► END
    """
    g = StateGraph(RiskAnalysisState)

    # ── Register nodes ──────────────────────────────────────────────────────
    g.add_node("input_validator",        input_validator)
    g.add_node("context_node",            context_node)
    g.add_node("payload_builder_node",   payload_builder_node)
    g.add_node("A5_detection_agent",     A5_detection_agent)
    g.add_node("A1_similar_cases_agent", A1_similar_cases_agent)
    g.add_node("A2_pattern_agent",       A2_pattern_agent)
    g.add_node("A3_severity_agent",      A3_severity_agent)
    g.add_node("A4_occurrence_agent",    A4_occurrence_agent)
    g.add_node("rpn_calculator_node",    rpn_calculator_node)
    g.add_node("A6_regulatory_agent",    A6_regulatory_agent)
    g.add_node("A7_reasoning_agent",     A7_reasoning_agent)
    g.add_node("finalize_node",          finalize_node)

    # ── Entry ────────────────────────────────────────────────────────────────
    g.add_edge(START, "input_validator")

    # ── Validation gate ──────────────────────────────────────────────────────
    # Pass  → intent_node
    # Fail  → END
    g.add_conditional_edges(
        "input_validator",
        route_after_validation,
        {"context_node": "context_node", END: END}
    )

    # ── Sequential: context → payload builder ───────────────────────────────
    g.add_edge("context_node", "payload_builder_node")

    # ── Fan-out: same as before ──────────────────────────────
    g.add_conditional_edges(
        "payload_builder_node",
        dispatch_parallel,          # fires A1, A2, A3, A5 together
        ["A1_similar_cases_agent",
        "A2_pattern_agent",
        "A3_severity_agent",
        "A5_detection_agent"]
    )

    # ── Fan-in: Synchronize all parallel agents ────────────────
    # LangGraph natively runs nodes immediately when triggered.
    # To prevent 'rpn_calculator_node' from running multiple times prematurely,
    # we enforce single fan-in by pointing ALL parallel agents to A4.
    # A4 only uses A1 and A2 internally, but acts as a structural barrier.
    g.add_edge("A1_similar_cases_agent", "A4_occurrence_agent")
    g.add_edge("A2_pattern_agent",       "A4_occurrence_agent")
    g.add_edge("A3_severity_agent",      "A4_occurrence_agent")
    g.add_edge("A5_detection_agent",     "A4_occurrence_agent")

    # ── RPN fan-in: runs sequentially AFTER A4 ────────────────
    g.add_edge("A4_occurrence_agent",    "rpn_calculator_node")

    # ── Sequential after RPN ──────────────────────────────────
    g.add_edge("rpn_calculator_node",    "A6_regulatory_agent")
    g.add_edge("A6_regulatory_agent",    "A7_reasoning_agent")
    g.add_edge("A7_reasoning_agent",     "finalize_node")
    g.add_edge("finalize_node",          END)
    

    # ── Compile with Redis checkpointing ─────────────────────────────────────
    # State saved after every node.
    # Crash recovery: resume from last checkpoint.
    # thread_id in config identifies the workflow.
    checkpointer = RedisSaver(redis_client=redis_client)

    return g.compile(checkpointer=checkpointer)


# ── Module-level graph instance ───────────────────────────────────────────────
# Import this in router.py
# Pass thread_id in config for checkpointing:
#   config = {"configurable": {"thread_id": "complaint-C4821"}}
#   result = orchestrator_graph.invoke({"raw_input": "..."}, config=config)
# orchestrator_graph = build_orchestrator()
orchestrator_graph = build_orchestrator()