"""
Agent Nodes
All node functions for the Zero Evidence Agent.

Node responsibilities:
  1. initialize_node        — Set up defaults in state
  2. validate_input_node    — Ensure causes list is non-empty
  3. llm_evaluate_node      — LLM identifies single point failure & safety risk per cause
  4. score_causes_node      — Deterministic scoring using the criticality_ranker tool
  5. select_cause_node      — Pick the single most critical cause
  6. finalize_node          — Package final output, end the graph
"""

import json
from typing import Any, Dict, List

from .state import AgentState
from .prompt import (
    ZERO_EVIDENCE_SYSTEM_PROMPT,
    ZERO_EVIDENCE_USER_PROMPT_TEMPLATE,
)
from .tools.criticality_ranker import compute_criticality_scores, select_top_cause
from .logger import (
    log_node_entry,
    log_node_exit,
    log_routing_decision,
    log_error,
    log_scoring,
)
from config.aws_bedrock_config import get_llm

from langgraph.graph import END


# ============================================================================
# HELPERS
# ============================================================================

def _format_causes_for_prompt(causes: List[Dict[str, Any]]) -> str:
    """Format the causes list into a human-readable string for the prompt."""
    lines = []
    for i, cause in enumerate(causes, 1):
        lines.append(f"Cause {i}:")
        lines.append(f"  cause_id        : {cause.get('cause_id', 'N/A')}")
        lines.append(f"  cause_text      : {cause.get('cause_text', 'N/A')}")
        lines.append(f"  process_step    : {cause.get('process_step', 'N/A')}")
        lines.append(f"  failure_mode    : {cause.get('failure_mode', 'N/A')}")
        lines.append(f"  potential_effects: {cause.get('potential_effects', 'N/A')}")
        lines.append(f"  severity        : {cause.get('severity', 'N/A')}")
        lines.append(f"  current_controls: {cause.get('current_controls', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


# ============================================================================
# NODE 1 — Initialize
# ============================================================================

def initialize_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state with safe defaults.
    Single responsibility: Prepare the working state.
    """
    log_node_entry("initialize", state)

    updates = {
        "iteration": 0,
        "max_iterations": 5,
        "llm_evaluations": None,
        "scored_causes": None,
        "selected_cause_id": None,
        "selected_cause_text": None,
        "selected_cause_process_step": None,
        "selection_reason": None,
        "confidence_level": None,
        "error": None,
        "next_step": "validate_input",
    }

    log_node_exit("initialize", updates)
    return updates


# ============================================================================
# NODE 2 — Validate Input
# ============================================================================

def validate_input_node(state: AgentState) -> AgentState:
    """
    Node: Validate that causes are present and non-empty.
    Single responsibility: Guard against empty input.
    """
    log_node_entry("validate_input", state)

    causes = state.get("causes", [])

    if not causes:
        error_msg = "Zero Evidence Agent received an empty causes list — cannot proceed."
        log_error("validate_input", error_msg)
        updates = {
            "error": error_msg,
            "next_step": END,
        }
        log_routing_decision("validate_input", "END", "Empty causes list")
        log_node_exit("validate_input", updates)
        return updates

    updates = {
        "next_step": "llm_evaluate",
    }
    log_routing_decision("validate_input", "llm_evaluate", f"{len(causes)} causes found")
    log_node_exit("validate_input", updates)
    return updates


# ============================================================================
# NODE 3 — LLM Evaluate
# ============================================================================

def llm_evaluate_node(state: AgentState) -> AgentState:
    """
    Node: Use Bedrock LLM to evaluate single point failure potential
    and safety risk for each cause.

    The LLM ONLY evaluates — it does NOT generate new causes.
    """
    log_node_entry("llm_evaluate", state)

    try:
        llm = get_llm()

        causes = state["causes"]
        question = state["question"]

        causes_text = _format_causes_for_prompt(causes)

        user_prompt = ZERO_EVIDENCE_USER_PROMPT_TEMPLATE.format(
            question=question,
            causes_text=causes_text,
        )

        full_prompt = ZERO_EVIDENCE_SYSTEM_PROMPT + "\n\n" + user_prompt

        response = llm.invoke(full_prompt)

        # The BedrockLLM client returns the extracted {…} JSON object in response.content.
        # Our prompt wraps the list under {"evaluations": [...]} so we parse that key.
        parsed = json.loads(response.content)
        evaluations = parsed.get("evaluations", [])

        if not isinstance(evaluations, list):
            raise ValueError("LLM did not return a JSON array of evaluations")

        updates = {
            "llm_evaluations": evaluations,
            "next_step": "score_causes",
            "iteration": state.get("iteration", 0) + 1,
        }
        log_routing_decision("llm_evaluate", "score_causes", f"{len(evaluations)} evaluations received")
        log_node_exit("llm_evaluate", {"next_step": "score_causes", "eval_count": len(evaluations)})
        return updates

    except Exception as e:
        error_msg = f"LLM evaluation failed: {str(e)}"
        log_error("llm_evaluate", error_msg)

        # Graceful degradation: continue with empty evaluations so scoring
        # falls back to severity-only ranking.
        updates = {
            "llm_evaluations": [],
            "error": error_msg,
            "next_step": "score_causes",
        }
        log_routing_decision("llm_evaluate", "score_causes", "LLM failed — using empty evaluations")
        log_node_exit("llm_evaluate", updates)
        return updates


# ============================================================================
# NODE 4 — Score Causes
# ============================================================================

def score_causes_node(state: AgentState) -> AgentState:
    """
    Node: Compute the composite criticality score for every cause
    using the deterministic ranking tool.

    No LLM call is made here.
    """
    log_node_entry("score_causes", state)

    try:
        causes = state["causes"]
        llm_evaluations = state.get("llm_evaluations") or []
        question = state["question"]

        scored = compute_criticality_scores(causes, llm_evaluations, question)

        # Log individual scores
        for entry in scored:
            log_scoring(
                entry["cause_id"],
                entry["final_score"],
                {
                    "severity": entry["severity"],
                    "spf_score": entry["single_point_failure_score"],
                    "sys_dep_score": entry["system_dependency_score"],
                    "safety_score": entry["safety_impact_score"],
                },
            )

        updates = {
            "scored_causes": scored,
            "next_step": "select_cause",
        }
        log_routing_decision("score_causes", "select_cause", f"Scored {len(scored)} causes")
        log_node_exit("score_causes", {"next_step": "select_cause", "scored_count": len(scored)})
        return updates

    except Exception as e:
        error_msg = f"Cause scoring failed: {str(e)}"
        log_error("score_causes", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize",
        }
        log_routing_decision("score_causes", "finalize", "Scoring exception — going to finalize")
        log_node_exit("score_causes", updates)
        return updates


# ============================================================================
# NODE 5 — Select Cause
# ============================================================================

def select_cause_node(state: AgentState) -> AgentState:
    """
    Node: Select the single Most Critical Functional Cause
    from the scored list.
    """
    log_node_entry("select_cause", state)

    try:
        scored_causes = state.get("scored_causes") or []

        if not scored_causes:
            raise ValueError("No scored causes available for selection")

        selected = select_top_cause(scored_causes)

        reason = (
            f"Highest criticality score ({selected['final_score']:.2f}) — "
            f"severity={selected['severity']}, "
            f"single_point_failure={selected['single_point_failure']}, "
            f"safety_risk={selected['safety_risk']}. "
            f"LLM reasoning: {selected['llm_reason']}"
        )

        updates = {
            "selected_cause_id": selected["cause_id"],
            "selected_cause_text": selected["cause_text"],
            "selected_cause_process_step": selected["process_step"],
            "selection_reason": reason,
            "confidence_level": "MEDIUM",
            "next_step": "finalize",
        }
        log_routing_decision("select_cause", "finalize", f"Selected: {selected['cause_id']}")
        log_node_exit("select_cause", {
            "selected_cause_id": selected["cause_id"],
            "final_score": selected["final_score"],
            "next_step": "finalize"
        })
        return updates

    except Exception as e:
        error_msg = f"Cause selection failed: {str(e)}"
        log_error("select_cause", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize",
        }
        log_routing_decision("select_cause", "finalize", "Selection exception")
        log_node_exit("select_cause", updates)
        return updates


# ============================================================================
# NODE 6 — Finalize
# ============================================================================

def finalize_node(state: AgentState) -> AgentState:
    """
    Node: Finalize output and signal graph completion.
    Single responsibility: Prepare the state for return.
    """
    log_node_entry("finalize", state)

    updates = {
        "next_step": END,
        "iteration": state.get("iteration", 0) + 1,
    }

    log_routing_decision("finalize", "END", "Zero Evidence Mode complete")
    log_node_exit("finalize", updates)
    return updates
