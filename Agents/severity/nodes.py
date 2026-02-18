"""
nodes.py

Defines processing nodes for the Severity Agent graph.

Nodes:
1. severity_llm_node
   - Uses LLM to classify issue into 4 severity dimensions

2. severity_calculation_node
   - Applies weighted formula
   - Maps final score to severity label

Each node:
- Logs entry and exit
- Updates shared state
- Raises exceptions if validation fails
"""


import json
from state import SeverityState
from config.aws_bedrock_config import get_llm
from prompts import build_severity_prompt
from tools.tools import load_matrix
from model import SeverityLLMOutput
from logger import (
    log_node_entry,
    log_node_exit,
    log_error
)
from tools.tools import (
    load_matrix,
    calculate_weighted_severity,
    get_severity_label
)


# ----------------------------------------
# NODE 1: score Classification
# ----------------------------------------
# Uses Groq LLM to map issue text to:
# - clinical_score
# - reversibility_score
# - medical_score
# - duration_score
#
# Enforces strict JSON output validation using Pydantic model.
# ----------------------------------------

# -------------------------
# NODE 1 —  Score Classification
# -------------------------
def severity_classification_node(state: SeverityState) -> SeverityState:
    log_node_entry("severity_llm_node", state)

    try:
        matrix_data = load_matrix()
        llm = get_llm()

        prompt = build_severity_prompt(
            state["issue"],
            matrix_data["SEVERITY_MATRIX"]
        )

        response = llm.invoke(prompt)
        parsed = SeverityLLMOutput(**json.loads(response.content))


        state["clinical_score"] = parsed.clinical_score
        state["reversibility_score"] = parsed.reversibility_score
        state["medical_score"] = parsed.medical_score
        state["duration_score"] = parsed.duration_score

        log_node_exit("severity_llm_node", state)
        return state

    except Exception as e:
        log_error("severity_llm_node", str(e))
        raise


# ----------------------------------------
# NODE 2: Weighted Severity Calculation
# ----------------------------------------
# Applies matrix-configured weights:
#   clinical * 0.4
#   reversibility * 0.2
#   medical * 0.25
#   duration * 0.15
#
# Rounds final score and clamps between 1–10.
# Maps numeric score to severity label.
# ----------------------------------------

# -------------------------
# NODE 2 — Weighted Calculation
# -------------------------
def severity_calculation_node(state: SeverityState) -> SeverityState:
    log_node_entry("severity_calculation_node", state)

    try:
        matrix_data = load_matrix()

        final_score = calculate_weighted_severity(
            state["clinical_score"],
            state["reversibility_score"],
            state["medical_score"],
            state["duration_score"],
            matrix_data,
        )

        state["severity_score"] = final_score
        state["severity_label"] = get_severity_label(final_score, matrix_data)

        log_node_exit("severity_calculation_node", state)
        return state

    except Exception as e:
        log_error("severity_calculation_node", str(e))
        raise
