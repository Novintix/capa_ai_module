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
    Node: Initialize state with input validation
    Single responsibility: Prepare the working state and validate inputs
    """
    log_node_entry("initialize", state)
    
    # Validate required inputs
    question = state.get("question", "").strip()
    question_id = state.get("question_id", "").strip()
    
    if not question_id:
        error_msg = "Invalid input: 'question_id' is required and cannot be empty"
        log_error("initialize", error_msg)
        updates = {
            "error": error_msg,
            "next_step": END,
        }
        log_routing_decision("initialize", "END", "Invalid question_id")
        log_node_exit("initialize", updates)
        return updates
    
    if not question:
        error_msg = "Invalid input: 'question' is required and cannot be empty"
        log_error("initialize", error_msg)
        updates = {
            "error": error_msg,
            "next_step": END,
        }
        log_routing_decision("initialize", "END", "Invalid question")
        log_node_exit("initialize", updates)
        return updates
    
    if len(question) < 5:
        error_msg = f"Invalid input: Question too short (minimum 5 characters). Received: '{question}'"
        log_error("initialize", error_msg)
        updates = {
            "error": error_msg,
            "next_step": END,
        }
        log_routing_decision("initialize", "END", "Question too short")
        log_node_exit("initialize", updates)
        return updates

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
    Node: Validate that causes are present, non-empty, and well-formed.
    Single responsibility: Guard against invalid input.
    """
    log_node_entry("validate_input", state)

    causes = state.get("causes", [])

    # Check if causes list exists and is not empty
    if not causes:
        error_msg = "Invalid input: Zero Evidence Agent received an empty causes list — cannot proceed."
        log_error("validate_input", error_msg)
        updates = {
            "error": error_msg,
            "next_step": END,
        }
        log_routing_decision("validate_input", "END", "Empty causes list")
        log_node_exit("validate_input", updates)
        return updates
    
    # Validate causes structure
    invalid_causes = []
    for i, cause in enumerate(causes):
        if not isinstance(cause, dict):
            invalid_causes.append(f"Cause {i}: Not a dictionary")
            continue
        
        # Check required fields
        if not cause.get("cause_id"):
            invalid_causes.append(f"Cause {i}: Missing 'cause_id'")
        if not cause.get("cause_text"):
            invalid_causes.append(f"Cause {i}: Missing 'cause_text'")
        if not cause.get("process_step"):
            invalid_causes.append(f"Cause {i}: Missing 'process_step'")
        if not cause.get("failure_mode"):
            invalid_causes.append(f"Cause {i}: Missing 'failure_mode'")
    
    if invalid_causes:
        error_msg = f"Invalid input: Causes have structural issues: {'; '.join(invalid_causes[:3])}"
        if len(invalid_causes) > 3:
            error_msg += f" (and {len(invalid_causes) - 3} more)"
        log_error("validate_input", error_msg)
        updates = {
            "error": error_msg,
            "next_step": END,
        }
        log_routing_decision("validate_input", "END", "Invalid cause structure")
        log_node_exit("validate_input", updates)
        return updates

    updates = {
        "next_step": "llm_evaluate",
    }
    log_routing_decision("validate_input", "llm_evaluate", f"{len(causes)} valid causes found")
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
    from the scored list and calculate confidence score.
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
            f"safety_risk={selected['safety_risk']}, "
            f"safety_blocking={selected.get('safety_blocking', 'none')}. "
            f"LLM reasoning: {selected['llm_reason']}"
        )

        # Calculate numerical confidence score (0.0-1.0) based on:
        # 1. Final score magnitude (higher score = higher confidence)
        # 2. Score separation from second-best cause (larger gap = higher confidence)
        # 3. LLM evaluation quality (has reasoning = higher confidence)
        # 4. Severity level (higher severity = higher confidence in selection)
        
        final_score = selected['final_score']
        severity = selected['severity']
        has_llm_reasoning = selected['llm_reason'] != "No LLM evaluation available"
        
        # Base confidence from final score (normalized to 0-1)
        # Max possible score is 10 (all factors at max), typical range is 3-8
        score_confidence = min(1.0, final_score / 10.0)
        
        # Separation factor: how much better is this than second-best?
        if len(scored_causes) > 1:
            second_score = scored_causes[1]['final_score']
            score_gap = final_score - second_score
            # Gap of 2+ points = high confidence, 0 gap = lower confidence
            separation_factor = min(1.0, 0.7 + (score_gap / 10.0))
        else:
            # Only one cause = moderate confidence
            separation_factor = 0.75
        
        # LLM evaluation quality factor
        llm_factor = 1.0 if has_llm_reasoning else 0.85
        
        # Severity factor (higher severity = more confident in selection)
        if severity >= 8:
            severity_factor = 1.0
        elif severity >= 6:
            severity_factor = 0.95
        elif severity >= 4:
            severity_factor = 0.85
        else:
            severity_factor = 0.75
        
        # Composite confidence score
        confidence_score = score_confidence * separation_factor * llm_factor * severity_factor
        
        # Ensure confidence is in valid range
        confidence_score = max(0.0, min(1.0, confidence_score))

        updates = {
            "selected_cause_id": selected["cause_id"],
            "selected_cause_text": selected["cause_text"],
            "selected_cause_process_step": selected["process_step"],
            "selection_reason": reason,
            "confidence_level": round(confidence_score, 2),  # Numerical score instead of label
            "next_step": "finalize",
        }
        log_routing_decision("select_cause", "finalize", f"Selected: {selected['cause_id']}, confidence: {confidence_score:.2f}")
        log_node_exit("select_cause", {
            "selected_cause_id": selected["cause_id"],
            "final_score": selected["final_score"],
            "confidence_score": confidence_score,
            "next_step": "finalize"
        })
        return updates

    except Exception as e:
        error_msg = f"Cause selection failed: {str(e)}"
        log_error("select_cause", error_msg)
        updates = {
            "error": error_msg,
            "confidence_level": 0.0,  # Zero confidence on error
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
