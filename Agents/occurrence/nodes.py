import json
import re
from Agents.occurrence.state import OccurrenceState, OccurrenceScoreResponse, OccurrenceOutput
from Agents.occurrence.utils import build_prompt, get_weights, build_evidence_summary
from config.aws_bedrock_config import get_llm
from Agents.occurrence.logger import (
    log_prompt, log_raw_response, log_score_audit,
    log_weighted_calculation, log_error,
    log_node_start, log_node_end
)

# Maps parameter codes to their occurrence_factors key names
PARAM_FACTOR_KEYS = {
    "HF": "Historical Frequency of Events",
    "TR": "Trend Analysis / Pattern Recognition",
    "PS": "Process Stability / Cp-Cpk Variability",
    "PC": "Effectiveness of Preventive Controls",
    "DM": "Effectiveness of Detection / Monitoring",
    "SY": "Systemic vs Isolated Issue",
    "OE": "Operator / Equipment Factors",
    "CA": "CAPA / Past Corrective Actions Effectiveness",
    "SU": "Supplier / External Factors",
    "AU": "Audit / Compliance Findings",
}



# ─────────────────────────────────────────────────────────────
# NODE 1: prepare_evidence
# DO #2: Single responsibility — only builds evidence summary
# DO #5: Separated from LLM call (orchestration vs processing)
def prepare_evidence(state: OccurrenceState) -> dict:
    """
    Node 1: Pre-computes a deterministic evidence summary per parameter
    from pattern data and similar cases. Now fully dynamic based on metrics.
    """
    # Auto-reset logs at the very start of a fresh run (iteration 0)
    if state.iteration == 0:
        from Agents.occurrence.logger import clear_logs
        clear_logs()

    log_node_start("prepare_evidence")

    input_data = state.input

    # Get dynamic parameter mapping from metrics
    metrics = None
    if hasattr(input_data, "metrics_data") and input_data.metrics_data:
        try:
            metrics = json.loads(input_data.metrics_data)
        except Exception:
            metrics = None
    
    if metrics is None:
        from Agents.occurrence.utils import load_metrics
        metrics = load_metrics.invoke({})
    
    # Build dynamic parameter factor keys from metrics
    param_factor_keys = {}
    parameters = metrics.get("parameters", {})
    
    if parameters:
        # Use whatever parameters are defined in metrics
        param_factor_keys = {
            code: param.get("name", code) 
            for code, param in parameters.items()
        }
    else:
        # Fallback to default parameters
        param_factor_keys = PARAM_FACTOR_KEYS

    # Extract similar cases from new structured format or legacy format
    similar_cases = []
    
    if input_data.similar_cases_data and input_data.similar_cases_data.topMatches:
        # Convert new format to legacy format for evidence building
        for match in input_data.similar_cases_data.topMatches:
            similar_case = {
                "complaint_id": match.complaintId,
                "record_id": match.recordId,
                "date": match.dateReceived,
                "source": match.source,
                "severity": match.severity,
                "product_family": match.productFamily,
                "site": match.site,
                "description": match.descriptionOfIssue,
                "status": match.status,
                "days_open": match.daysOpen,
                "assigned_to": match.assignedTo,
                "capa_needed": match.capaNeeded,
                "capa_id": match.capaId,
                "capa_rationale": match.capaRationale,
                "repeated": match.repeated,
                "workflow_stage": match.workflowStage,
                "similarity": match.similarity,
                "region_country": match.regionCountry,
                "field_action": match.fieldAction,
                "eu_reportable": match.euReportable,
                "fda_reportable": match.fdaReportable
            }
            similar_cases.append(similar_case)
    elif input_data.similar_cases:
        # Use legacy format
        similar_cases = input_data.similar_cases

    # Build evidence summary with dynamic parameters
    evidence_summary = build_evidence_summary(
        similar_cases=similar_cases,
        param_factor_keys=param_factor_keys,
        pattern_data=input_data.pattern_data
    )

    log_node_end(
        "prepare_evidence",
        f"Evidence built for {len(evidence_summary)} parameters from {len(similar_cases)} case(s) and pattern data"
    )

    return {
        "iteration": state.iteration + 1,
        "evidence_summary": evidence_summary
    }


# DO #4: Max Retries for LLM calls (handling network/parsing failures)
MAX_RETRIES = 3

# ─────────────────────────────────────────────────────────────
# NODE 2: generate_scores
# DO #2: Single responsibility — only calls LLM and parses scores
# ─────────────────────────────────────────────────────────────
def generate_scores(state: OccurrenceState) -> dict:
    """
    Node 2: Calls LLM once with pre-computed evidence and parses scores.
    Uses evidence-first chain-of-thought anchoring for consistent scoring.
    Retries up to MAX_RETRIES if LLM fails or returns invalid JSON.
    """
    log_node_start("generate_scores")

    input_data = state.input

    # Check for max retries
    if state.iteration > MAX_RETRIES:
        error_msg = f"Max retries ({MAX_RETRIES}) reached for generate_scores. Aborting."
        log_error("generate_scores", error_msg)
        raise RuntimeError(error_msg)

    metrics = None
    if hasattr(input_data, "metrics_data") and input_data.metrics_data:
        try:
            metrics = json.loads(input_data.metrics_data)
        except Exception:
            metrics = None

    # Retrieve pre-computed evidence from state (set by prepare_evidence node)
    # DON'T #7: evidence_summary is declared in OccurrenceState — no hidden state
    evidence_summary = state.evidence_summary

    # DO #6: Defensive guard — fallback if evidence not in state
    if evidence_summary is None:
        evidence_summary = build_evidence_summary(
            similar_cases=input_data.similar_cases or [],
            param_factor_keys=PARAM_FACTOR_KEYS
        )

    prompt = build_prompt(
        description=input_data.description,
        product=input_data.product,
        date=input_data.date,
        context=input_data.additional_context or "None",
        metrics=metrics,
        evidence_summary=evidence_summary
    )

    log_prompt(prompt)

    try:
        llm = get_llm()
        response = llm.invoke(prompt)

        log_raw_response(response.raw_content, run_number=state.iteration + 1)

        # Advanced JSON extraction with multiple fallback strategies
        raw_content = response.content
        json_str = None
        
        # Strategy 1: Try to find JSON object (greedy from first { to last })
        first_brace = raw_content.find('{')
        last_brace = raw_content.rfind('}')
        if first_brace >= 0 and last_brace > first_brace:
            potential_json = raw_content[first_brace:last_brace + 1]
            try:
                content = json.loads(potential_json)
                json_str = potential_json
            except json.JSONDecodeError:
                # Strategy 2: Try to extract from code blocks
                code_block_match = re.search(r'```(?:json)?\s*({.*?})\s*```', raw_content, re.DOTALL)
                if code_block_match:
                    try:
                        content = json.loads(code_block_match.group(1))
                        json_str = code_block_match.group(1)
                    except json.JSONDecodeError:
                        pass
        
        if json_str is None:
            # Strategy 3: Try entire response as JSON
            try:
                content = json.loads(raw_content)
                json_str = raw_content
            except json.JSONDecodeError as e:
                log_error("generate_scores", 
                    f"JSON extraction failed (tried 3 strategies):\n"
                    f"Error: {str(e)}\n"
                    f"Raw response:\n{raw_content}")
                raise RuntimeError(f"Could not extract valid JSON from LLM response: {str(e)}")
        
        # Handle both old and new response formats
        if "scores" in content and isinstance(content["scores"], dict):
            # New dynamic format
            scores = OccurrenceScoreResponse(scores=content["scores"], reasoning=content.get("reasoning", ""))
        else:
            # Legacy format or direct parameter mapping
            # Extract parameter scores dynamically
            param_scores = {}
            reasoning = content.get("reasoning", "")
            
            # Get expected parameters from metrics
            if metrics:
                expected_params = list(metrics.get("parameters", {}).keys())
            else:
                # Fallback to legacy parameters
                expected_params = ["HF", "TR", "PS", "PC", "DM", "SY", "OE", "CA", "SU", "AU"]
            
            # Extract scores for expected parameters
            for param in expected_params:
                if param in content:
                    param_scores[param] = content[param]
                else:
                    param_scores[param] = 1  # Default score
            
            scores = OccurrenceScoreResponse(scores=param_scores, reasoning=reasoning)
        log_score_audit(content, input_data.similar_cases or [])

        log_node_end("generate_scores", f"Scores parsed for 10 parameters")

        # Success! Return scores (and keep iteration same or increment?
        # Does not matter much, but let's just return scores)
        # We DO NOT increment iteration on success to avoid triggering retry logic if checks depend on it
        # But actually we track attempts via iteration.
        return {"raw_scores": scores}

    except Exception as e:
        log_error("generate_scores", f"Attempt {state.iteration + 1} failed: {str(e)}")
        # RETRY LOGIC: Increment iteration count and return (no scores)
        # The conditional edge in graph.py will see raw_scores is None and route back here.
        return {"iteration": state.iteration + 1}


# ─────────────────────────────────────────────────────────────
# NODE 3: calculate_weighted_score
# DO #2: Single responsibility — only computes final score
# DO #6: Guards that raw_scores exist and values are in range
# ─────────────────────────────────────────────────────────────
def calculate_weighted_score(state: OccurrenceState) -> dict:
    """
    Node 3: Computes the final weighted score from raw scores.
    Now handles dynamic parameter sets from any metrics configuration.
    """
    log_node_start("calculate_weighted_score")

    # DO #6: Guard — raw_scores must exist before routing here
    scores = state.raw_scores
    if not scores:
        raise ValueError("State guard failed: raw_scores is None before calculate_weighted_score")

    input_data = state.input

    metrics = None
    if hasattr(input_data, "metrics_data") and input_data.metrics_data:
        try:
            metrics = json.loads(input_data.metrics_data)
        except Exception:
            metrics = None

    weights = get_weights.invoke({"metrics": metrics} if metrics is not None else {})

    # Build score dictionary dynamically from whatever parameters exist
    score_dict = {}
    if hasattr(scores, 'scores') and isinstance(scores.scores, dict):
        # New dynamic format
        score_dict = scores.scores.copy()
    else:
        # Legacy format - try to extract known parameters
        legacy_params = ['HF', 'TR', 'PS', 'PC', 'DM', 'SY', 'OE', 'CA', 'SU', 'AU']
        for param in legacy_params:
            if hasattr(scores, param):
                score_dict[param] = getattr(scores, param)

    # Ensure all weighted parameters have scores
    for param_code in weights.keys():
        if param_code not in score_dict:
            score_dict[param_code] = 1  # Default score

    # DO #6: Clamp scores to valid range as a safety net
    score_dict = {k: max(1, min(10, v)) for k, v in score_dict.items()}

    weighted_sum = sum(score_dict.get(code, 1) * weights.get(code, 0) for code in weights.keys())

    log_weighted_calculation(scores, weights)

    rating_map = {
        1: "Remote",
        2: "Very Low",
        3: "Low",
        4: "Low-Moderate",
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
        weighted_score=rounded_score,
        rating=rating,
        breakdown=scores
    )

    log_node_end(
        "calculate_weighted_score",
        f"weighted_score={rounded_score} | rating={rating}"
    )

    # DON'T #1: Return dict — let LangGraph merge state
    return {"final_output": output}
