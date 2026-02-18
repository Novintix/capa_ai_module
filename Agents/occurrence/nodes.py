import json
from Agents.occurrence.state import OccurrenceState, OccurrenceScoreResponse, OccurrenceOutput
from Agents.occurrence.utils import build_prompt, get_weights
from config.aws_bedrock_config import get_llm
from Agents.occurrence.logger import (
    log_prompt, log_raw_response, log_score_audit,
    log_weighted_calculation, log_error
)


def generate_scores(state: OccurrenceState):
    """
    Node to call LLM and generate occurrence scores for each parameter.
    Loads metrics from metrics.json (or from uploaded metrics data in state).
    """
    input_data = state.input

    # Load metrics — use uploaded metrics if provided, else default metrics.json
    metrics = None
    if hasattr(input_data, "metrics_data") and input_data.metrics_data:
        try:
            metrics = json.loads(input_data.metrics_data)
        except Exception:
            metrics = None  # Fall back to default if parse fails

    # Format similar cases for the prompt
    similar_cases_str = (
        json.dumps(input_data.similar_cases, indent=2)
        if input_data.similar_cases
        else "None"
    )

    # Build prompt dynamically from metrics
    prompt = build_prompt(
        description=input_data.description,
        product=input_data.product,
        date=input_data.date,
        similar_cases=similar_cases_str,
        context=input_data.additional_context or "None",
        metrics=metrics
    )

    # Log the full prompt sent to the LLM
    log_prompt(prompt)

    try:
        llm = get_llm()
        response = llm.invoke(prompt)

        # Log the raw LLM response before any parsing
        log_raw_response(response.raw_content)

        # Parse response content
        content = json.loads(response.content)

        # Create score response object
        scores = OccurrenceScoreResponse(**content)

        # Deep audit: score vs rubric vs input evidence (hallucination detection)
        log_score_audit(content, input_data.similar_cases or [])

        return {"raw_scores": scores}

    except Exception as e:
        log_error("generate_scores", str(e))
        raise RuntimeError(f"Error generating scores: {str(e)}")


def calculate_weighted_score(state: OccurrenceState):
    """
    Node to calculate the final weighted score based on raw scores and weights.
    Loads weights from metrics.json (or from uploaded metrics data in state).
    """
    scores = state.raw_scores
    if not scores:
        raise ValueError("No raw scores found in state")

    input_data = state.input

    # Load weights from metrics
    metrics = None
    if hasattr(input_data, "metrics_data") and input_data.metrics_data:
        try:
            metrics = json.loads(input_data.metrics_data)
        except Exception:
            metrics = None

    weights = get_weights(metrics)

    # Calculate weighted sum
    score_dict = {
        "HF": scores.HF,
        "TR": scores.TR,
        "PS": scores.PS,
        "PC": scores.PC,
        "DM": scores.DM,
        "SY": scores.SY,
        "OE": scores.OE,
        "CA": scores.CA,
        "SU": scores.SU,
        "AU": scores.AU,
    }

    weighted_sum = sum(score_dict[code] * weights.get(code, 0) for code in score_dict)

    log_weighted_calculation(scores, weights)

    rating_map = {
        1: "Remote",
        2: "Very Low",
        3: "Low",
        4: "Low–Moderate",
        5: "Moderate",
        6: "Elevated Moderate",
        7: "High",
        8: "Very High",
        9: "Critical",
        10: "Almost Certain"
    }

    rounded_score = max(1, min(10, int(round(weighted_sum))))
    rating = rating_map.get(rounded_score, "Unknown")

    output = OccurrenceOutput(
        weighted_score=round(weighted_sum, 2),
        rating=rating,
        breakdown=scores
    )

    return {"final_output": output}
