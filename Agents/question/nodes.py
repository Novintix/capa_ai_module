"""
Agent Nodes
All node functions for the Why Question Agent.

RESPONSIBILITY:
  Each node has one job. Orchestration lives in graph.py.

NODES:
  initialize_state_node     — Set up defaults before processing starts.
  validate_inputs_node      — Confirm required inputs are present and non-empty.
  generate_why_question_node — Call the LLM to produce the next "Why?" question.
  finalize_node             — Package the output or surface the error cleanly.
"""

import json
import re

from .state import AgentState
from .prompt import WHY_QUESTION_SYSTEM_PROMPT, WHY_QUESTION_USER_PROMPT_TEMPLATE
from .logger import log_node_entry, log_node_exit, log_routing_decision, log_error
from config.aws_bedrock_config import get_llm


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def clean_llm_response(response_text: str) -> str:
    """Clean LLM response by removing reasoning tags and markdown."""
    # Strip reasoning tags if present
    if "<reasoning>" in response_text and "</reasoning>" in response_text:
        response_text = re.sub(r'<reasoning>.*?</reasoning>\s*', '', response_text, flags=re.DOTALL).strip()

    # Remove markdown code blocks
    response_text = response_text.replace('```json', '').replace('```', '').strip()

    # Extract JSON object — find first { and last }
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        response_text = response_text[start_idx:end_idx + 1]
    elif start_idx != -1:
        # JSON started but didn't close — try to recover
        response_text = response_text[start_idx:]
        if response_text.count('"') % 2 != 0:
            response_text += '"'
        response_text += '}'
    else:
        raise ValueError(f"No valid JSON object found in response")

    return response_text


def _format_previous_chain(
    previous_why: list,
    previous_answers: list
) -> str:
    """
    Interleave previous Why questions and their answers into a readable chain.

    Example output:
        1. Why did the seal fail?
           Answer: The sealing bar temperature was too low.
        2. Why was the sealing bar temperature too low?
           Answer: The pre-heat timer was never started.
    """
    if not previous_why:
        return "None — this is the first Why."

    answers = previous_answers or []
    lines = []
    for i, question in enumerate(previous_why):
        lines.append(f"{i + 1}. {question}")
        if i < len(answers) and answers[i]:
            lines.append(f"   Answer: {answers[i]}")
        else:
            lines.append("   Answer: (not provided)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def initialize_state_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state with safe defaults.
    Single responsibility: Prepare state before any processing.
    """
    log_node_entry("initialize", state)

    previous_why = state.get("previous_why") or []
    previous_answers = state.get("previous_answers") or []
    why_depth = len(previous_why) + 1  # Next depth level

    updates = {
        "iteration": 0,
        "max_iterations": 5,
        "validated": False,
        "why_depth": why_depth,
        "previous_why": previous_why,
        "previous_answers": previous_answers,
        "why_question": None,
        "reasoning": None,
        "error": None,
        "next_step": "validate_inputs"
    }

    log_node_exit("initialize", updates)
    return updates


def validate_inputs_node(state: AgentState) -> AgentState:
    """
    Node: Validate that all required inputs are present and non-empty.
    Single responsibility: Guard against incomplete requests.
    """
    log_node_entry("validate_inputs", state)

    missing = []

    if not state.get("complaint_id", "").strip():
        missing.append("complaint_id")
    if not state.get("complaint", "").strip():
        missing.append("complaint")
    if not state.get("evidence", "").strip():
        missing.append("evidence")
    if not state.get("sop", "").strip():
        missing.append("sop")

    if missing:
        error_msg = f"Missing or empty required fields: {', '.join(missing)}"
        log_error("validate_inputs", error_msg)
        log_routing_decision("validate_inputs", "finalize", error_msg)
        updates = {
            "validated": False,
            "error": error_msg,
            "next_step": "finalize"
        }
        log_node_exit("validate_inputs", updates)
        return updates

    log_routing_decision("validate_inputs", "generate_why_question", "All required inputs present")
    updates = {
        "validated": True,
        "error": None,
        "next_step": "generate_why_question"
    }
    log_node_exit("validate_inputs", updates)
    return updates


def generate_why_question_node(state: AgentState) -> AgentState:
    """
    Node: Call the LLM to generate the next "Why?" question.
    Single responsibility: LLM interaction and response parsing.
    """
    log_node_entry("generate_why_question", state)

    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 5)

    # Safety guard: prevent infinite retry loops
    if iteration >= max_iterations:
        error_msg = f"Max iterations ({max_iterations}) reached without a valid response."
        log_error("generate_why_question", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_node_exit("generate_why_question", updates)
        return updates

    try:
        llm = get_llm()

        user_prompt = WHY_QUESTION_USER_PROMPT_TEMPLATE.format(
            complaint=state["complaint"],
            evidence=state["evidence"],
            sop=state["sop"],
            previous_chain=_format_previous_chain(
                state.get("previous_why"),
                state.get("previous_answers")
            )
        )

        # Build the full prompt: system + user combined for the BedrockLLM interface
        full_prompt = (
            f"{WHY_QUESTION_SYSTEM_PROMPT}\n\n"
            f"---\n\n"
            f"{user_prompt}"
        )

        response = llm.invoke(full_prompt)
        response_text = clean_llm_response(response.content)
        parsed = json.loads(response_text)

        why_question = parsed.get("why_question", "").strip()
        reasoning = parsed.get("reasoning", "").strip()
        why_depth = parsed.get("why_depth", state.get("why_depth", 1))

        # Basic sanity: the question must start with "Why" (case-insensitive)
        if not why_question.lower().startswith("why"):
            raise ValueError(
                f"Generated question does not start with 'Why': {why_question!r}"
            )

        log_routing_decision("generate_why_question", "finalize", "Question generated successfully")
        updates = {
            "why_question": why_question,
            "reasoning": reasoning,
            "why_depth": why_depth,
            "iteration": iteration + 1,
            "error": None,
            "next_step": "finalize"
        }
        log_node_exit("generate_why_question", updates)
        return updates

    except json.JSONDecodeError as exc:
        error_msg = f"Failed to parse LLM JSON response: {exc}"
        log_error("generate_why_question", error_msg)
        updates = {
            "iteration": iteration + 1,
            "error": error_msg,
            "next_step": "finalize"
        }
        log_node_exit("generate_why_question", updates)
        return updates

    except Exception as exc:
        error_msg = f"Unexpected error during question generation: {exc}"
        log_error("generate_why_question", error_msg)
        updates = {
            "iteration": iteration + 1,
            "error": error_msg,
            "next_step": "finalize"
        }
        log_node_exit("generate_why_question", updates)
        return updates


def finalize_node(state: AgentState) -> AgentState:
    """
    Node: Package the final output or surface the error cleanly.
    Single responsibility: Ensure the agent always returns a consistent state.
    """
    log_node_entry("finalize", state)

    updates = {"next_step": "__end__"}

    if state.get("error") and not state.get("why_question"):
        # Surface error — output fields stay None
        log_routing_decision("finalize", "__end__", f"Finishing with error: {state['error']}")
    else:
        # Happy path — output is already set by generate_why_question_node
        log_routing_decision(
            "finalize",
            "__end__",
            f"Why question ready at depth {state.get('why_depth')}"
        )

    log_node_exit("finalize", updates)
    return updates
