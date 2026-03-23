"""
graph.py

LangGraph workflow for CAPA Effectiveness Evaluation Agent.

Flow:
  extract_evidence
        ↓
  evaluate_actions ←─────────────────┐
        ↓                            │ retry (on guardrail violation)
  validate_evaluations               │
        ↓                            │
   passed? ──── No (retry left) ─────┘
        │
       Yes
        ↓
       END
"""

from langgraph.graph import StateGraph, END
from .state import EffectivenessState
from .nodes import (
    extract_evidence_node,
    evaluate_actions_node,
    validate_evaluations_node,
    MAX_RETRIES,
)
from .logger import log_retry


def should_retry(state: EffectivenessState) -> str:
    """
    Conditional edge after validate_evaluations_node.
      - Error + retries remaining → retry (route back to evaluate_actions)
      - Error + retries exhausted → raise RuntimeError
      - No error                  → end
    """
    error       = state.get("error")
    retry_count = state.get("retry_count", 0)

    if error and retry_count < MAX_RETRIES:
        state["retry_count"] = retry_count + 1
        log_retry(
            retry_count + 1,
            MAX_RETRIES,
            state.get("validation_error_message", error)
        )
        return "retry"

    if error and retry_count >= MAX_RETRIES:
        raise RuntimeError(
            f"CAPA Effectiveness Evaluation failed after {MAX_RETRIES} retries. "
            f"Last violation: {state.get('validation_error_message', error)}"
        )

    return "end"


def build_graph():
    """Build and compile the CAPA effectiveness evaluation graph."""

    builder = StateGraph(EffectivenessState)

    builder.add_node("extract_evidence",     extract_evidence_node)
    builder.add_node("evaluate_actions",     evaluate_actions_node)
    builder.add_node("validate_evaluations", validate_evaluations_node)

    builder.set_entry_point("extract_evidence")
    builder.add_edge("extract_evidence",     "evaluate_actions")
    builder.add_edge("evaluate_actions",     "validate_evaluations")

    builder.add_conditional_edges(
        "validate_evaluations",
        should_retry,
        {
            "retry": "evaluate_actions",
            "end":   END,
        }
    )

    return builder.compile()