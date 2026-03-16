"""
nodes.py

Processing nodes for CAPA Effectiveness Evaluation generation.
Includes:
- evaluate_actions_node: Uses LLM to evaluate action plan effectiveness
"""

import json
import json_repair
from .state import EffectivenessState
from config.aws_bedrock_config import get_llm
from .prompts import build_effectiveness_evaluation_prompt
from .model import EffectivenessEvaluationResponse
from .logger import log_node_entry, log_node_exit, log_error, log_evaluation

def evaluate_actions_node(state: EffectivenessState) -> EffectivenessState:
    """
    NODE 1: Evaluate Actions
    Uses LLM to evaluate CAPA action plan effectiveness.
    """
    log_node_entry("evaluate_actions_node", state)
    try:
        llm = get_llm()
        evaluation_input = state.get("evaluation_input", {})

        # Build prompt
        prompt = build_effectiveness_evaluation_prompt(evaluation_input)

        # Invoke LLM
        response = llm.invoke(prompt)
        
        # Parse JSON response reliably
        content = response.content
        parsed_json = json_repair.loads(content)
        if isinstance(parsed_json, str):
            parsed_json = json_repair.loads(parsed_json)
        
        # Validate using Pydantic
        validated_response = EffectivenessEvaluationResponse(**parsed_json)

        # Store results in state
        state["evaluated_actions"] = [item.dict() for item in validated_response.evaluated_actions]
        # Sort actions by score descending
        state["evaluated_actions"].sort(key=lambda x: x["effectiveness_score"], reverse=True)
        
        state["confidence_score"] = validated_response.confidence_score
        state["notes"] = validated_response.notes

        log_evaluation(state["evaluated_actions"])
        log_node_exit("evaluate_actions_node", state)
        return state

    except Exception as e:
        log_error("evaluate_actions_node", str(e))
        state["error"] = str(e)
        raise

def validate_evaluations_node(state: EffectivenessState) -> EffectivenessState:
    """
    NODE 2: Validate Evaluations (API & Industry Guardrails)
    Validates the generated effectiveness scores and logic against CAPA/QMS standards.
    """
    log_node_entry("validate_evaluations_node", state)
    try:
        evaluated_actions = state.get("evaluated_actions", [])

        for action in evaluated_actions:
            score = action.get("effectiveness_score", 0)
            addressed = action.get("root_cause_addressed", "No")
            recurrence = action.get("recurrence_prevention_level", "Low")
            confidence = action.get("confidence_level", "Low")
            explanation = action.get("explanation_of_evaluation", "").strip()

            # Guardrail 1: Score bounding
            if score < 0 or score > 100:
                raise ValueError(f"Effectiveness score {score} for action {action['action_id']} is out of bounds.")
            
            # Guardrail 2: Root Cause Addressment Consistency
            # If the action doesn't address the root cause, it cannot be considered highly effective.
            if addressed == "No" and score > 40:
                raise ValueError(f"CAPA Violation: Action {action['action_id']} does not address the root cause but has an invalidly high score of {score}. Score must be <= 40.")
            if addressed == "Partially" and score > 75:
                raise ValueError(f"CAPA Violation: Action {action['action_id']} only partially addresses the root cause but has an invalidly high score of {score}. Score must be <= 75.")

            # Guardrail 3: Recurrence Prevention Consistency
            # ISO/FDA emphasize preventing recurrence. Low prevention capacity implies low effectiveness.
            if recurrence == "Low" and score > 60:
                raise ValueError(f"CAPA Violation: Action {action['action_id']} has 'Low' recurrence prevention but a high effectiveness score of {score}. Score must be <= 60.")

            # Guardrail 4: Confidence Level Checks
            # Highly effective ratings require at least medium confidence.
            if confidence == "Low" and score >= 80:
                raise ValueError(f"Audit Risk: Action {action['action_id']} scored {score} (High Effectiveness) but the evaluation confidence is 'Low'. High scores require robust justification and confidence.")

            # Guardrail 5: Substantive Justification
            # Regulatory bodies require clear, written justifications for effectiveness.
            if len(explanation) < 30:
                raise ValueError(f"Audit Risk: Action {action['action_id']} lacks a substantive explanation. A detailed justification (>30 characters) is required for QMS compliance.")

            # Guardrail 6: Excellent Score Criteria
            # An 'Excellent' score (>90) mandates that the action completely addresses the root cause AND prevents recurrence.
            if score >= 90 and (addressed != "Yes" or recurrence != "High"):
                raise ValueError(f"CAPA Violation: Action {action['action_id']} scored {score} (Excellent) but does not fully address the root cause or have High recurrence prevention.")

        state["error"] = None
        log_node_exit("validate_evaluations_node", state)
        return state

    except Exception as e:
        log_error("validate_evaluations_node", str(e))
        state["error"] = str(e)
        raise
