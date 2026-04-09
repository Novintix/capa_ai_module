"""
Node functions for Ranking Agent.
Each node performs a specific step in the RCPS calculation workflow.

Key optimisation (v2):
  evaluate_evidence + evaluate_mechanism + evaluate_proximity are replaced by a
  SINGLE evaluate_all_scores node that issues ONE LLM call per cause and parses
  all 3 scores from a JSON response.  LLM call count: 3N → N.
"""

import json
import re
from typing import Dict, Any
from Agents.ranking.state import RankingState, RankedCause, RankingOutput, RankingConfig
from Agents.ranking.logger import (
    log_node_start, log_node_end, log_rpn_calculation,
    log_normalization, log_evidence_eval, log_mechanism_eval,
    log_proximity_eval, log_rcps_calculation, log_final_ranking, log_error
)
from Agents.ranking.prompts import build_scores_prompt
from config.aws_bedrock_config import get_llm


def calculate_rpn(state: RankingState) -> Dict[str, Any]:
    """
    Node 1: Calculate Risk Priority Number (RPN) for each cause.
    RPN = Severity × Occurrence × Detection
    """
    log_node_start("calculate_rpn")
    
    try:
        causes = state.input.causes
        rpn_results = []
        
        for cause in causes:
            rpn = cause.severity * cause.occurrence * cause.detection
            
            result = {
                "cause_id": cause.cause_id,
                "cause_text": cause.cause_text,
                "context_step": cause.get_step(),
                "issue_type": cause.get_issue(),
                "impact_description": cause.get_impact(),
                "severity": cause.severity,
                "occurrence": cause.occurrence,
                "detection": cause.detection,
                "rpn": rpn,
                "metadata": cause.metadata
            }
            
            rpn_results.append(result)
            log_rpn_calculation(cause.cause_id, rpn)
        
        log_node_end("calculate_rpn", f"Calculated RPN for {len(rpn_results)} causes")
        return {"rpn_calculated": rpn_results}
        
    except Exception as e:
        error_msg = f"Failed to calculate RPN: {str(e)}"
        log_error("calculate_rpn", error_msg)
        return {"error": error_msg}



def normalize_rpn(state: RankingState) -> Dict[str, Any]:
    """
    Node 2: Normalize RPN scores to 0-1 range.
    RPN_score = RPN / Max_RPN
    """
    log_node_start("normalize_rpn")
    
    try:
        rpn_calculated = state.rpn_calculated
        
        # Find max RPN
        max_rpn = max(cause["rpn"] for cause in rpn_calculated)
        log_normalization(max_rpn, len(rpn_calculated))
        
        # Normalize each RPN
        normalized_results = []
        for cause in rpn_calculated:
            rpn_score = cause["rpn"] / max_rpn if max_rpn > 0 else 0
            
            result = {**cause, "rpn_score": rpn_score}
            normalized_results.append(result)
        
        log_node_end("normalize_rpn", f"Normalized {len(normalized_results)} RPN scores")
        return {"rpn_normalized": normalized_results}
        
    except Exception as e:
        error_msg = f"Failed to normalize RPN: {str(e)}"
        log_error("normalize_rpn", error_msg)
        return {"error": error_msg}


# ---------------------------------------------------------------------------
# Score defaults used as fallbacks when LLM parsing fails
# ---------------------------------------------------------------------------
_DEFAULT_EVIDENCE   = 0.5   # Historical level — conservative
_DEFAULT_MECHANISM  = 0.7   # Moderate fit — conservative
_DEFAULT_PROXIMITY  = 0.7   # Contributor — conservative

_ALLOWED_EVIDENCE   = {1.0, 0.7, 0.5, 0.3}
_ALLOWED_MECHANISM  = {0.9, 0.7, 0.4}
_ALLOWED_PROXIMITY  = {1.0, 0.7, 0.4}


def _snap_to_allowed(value: float, allowed: set, cause_id: str, field: str) -> float:
    """Snap a float to the nearest allowed value, logging if a correction was needed."""
    if value in allowed:
        return value
    snapped = min(allowed, key=lambda x: abs(x - value))
    log_error(
        "evaluate_all_scores",
        f"[{cause_id}] {field}={value} is not an allowed value — snapping to {snapped}"
    )
    return snapped


def _parse_scores_response(raw: str, cause_id: str) -> Dict[str, float]:
    """
    Parse the LLM JSON response for a cause.

    Handles:
    - Clean JSON objects: {"evidence_strength": 0.7, ...}
    - JSON wrapped in ```json ... ``` fences
    - Reasoning tags like <reasoning>...</reasoning>
    - Partial / malformed JSON (returns defaults)

    Returns:
        dict with evidence_strength, mechanism_fit, causal_proximity
    """
    defaults = {
        "evidence_strength": _DEFAULT_EVIDENCE,
        "mechanism_fit": _DEFAULT_MECHANISM,
        "causal_proximity": _DEFAULT_PROXIMITY,
    }

    try:
        text = raw

        # Strip reasoning tags if present
        text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL).strip()

        # Strip markdown fences
        text = re.sub(r'```(?:json)?', '', text).replace('```', '').strip()

        # Extract first valid JSON object
        start = text.find('{')
        end   = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response")
        parsed = json.loads(text[start:end + 1])

        evidence  = float(parsed.get("evidence_strength",  _DEFAULT_EVIDENCE))
        mechanism = float(parsed.get("mechanism_fit",       _DEFAULT_MECHANISM))
        proximity = float(parsed.get("causal_proximity",   _DEFAULT_PROXIMITY))

        return {
            "evidence_strength":  _snap_to_allowed(evidence,  _ALLOWED_EVIDENCE,  cause_id, "evidence_strength"),
            "mechanism_fit":      _snap_to_allowed(mechanism, _ALLOWED_MECHANISM, cause_id, "mechanism_fit"),
            "causal_proximity":   _snap_to_allowed(proximity, _ALLOWED_PROXIMITY, cause_id, "causal_proximity"),
        }

    except Exception as exc:
        log_error(
            "evaluate_all_scores",
            f"[{cause_id}] Failed to parse LLM response: {exc} | raw={raw[:200]!r} | Using defaults."
        )
        return defaults


def evaluate_all_scores(state: RankingState) -> Dict[str, Any]:
    """
    Node 3 (unified): Evaluate evidence_strength, mechanism_fit, AND causal_proximity
    for every cause in a SINGLE LLM call per cause.

    Replaces the old 3-node, 3-call-per-cause sequence:
        evaluate_evidence → evaluate_mechanism → evaluate_proximity

    LLM calls: 3N → N  (e.g. 30 → 10 for 10 causes)

    State output:
        evidence_evaluated   — populated for RCPS node compatibility
        mechanism_evaluated  — populated for RCPS node compatibility
        proximity_evaluated  — populated with all 3 scores merged
    """
    log_node_start("evaluate_all_scores")

    try:
        rpn_normalized = state.rpn_normalized
        config = state.input.config or RankingConfig()
        llm = get_llm()

        scored_causes = []

        for cause in rpn_normalized:
            prompt = build_scores_prompt(
                cause_text=cause["cause_text"],
                issue_type=cause["issue_type"],
                context_step=cause["context_step"],
                impact_description=cause["impact_description"],
                domain=config.domain,
                evidence_context=config.evidence_context,
                mechanism_context=config.mechanism_context,
                proximity_context=config.proximity_context,
            )

            response = llm.invoke(prompt)
            scores   = _parse_scores_response(response.content, cause["cause_id"])

            result = {
                **cause,
                "evidence_strength":  scores["evidence_strength"],
                "mechanism_fit":      scores["mechanism_fit"],
                "causal_proximity":   scores["causal_proximity"],
            }
            scored_causes.append(result)

            # Log each dimension (matches existing logger calls)
            log_evidence_eval(cause["cause_id"],  scores["evidence_strength"])
            log_mechanism_eval(cause["cause_id"], scores["mechanism_fit"])
            log_proximity_eval(cause["cause_id"], scores["causal_proximity"])

        log_node_end(
            "evaluate_all_scores",
            f"Scored {len(scored_causes)} causes ({len(scored_causes)} LLM calls — was {3 * len(scored_causes)})"
        )

        # Populate all 3 state fields so downstream nodes (calculate_rcps) stay unchanged
        return {
            "evidence_evaluated":  scored_causes,   # backward-compat alias
            "mechanism_evaluated": scored_causes,   # backward-compat alias
            "proximity_evaluated": scored_causes,   # passed directly to calculate_rcps
        }

    except Exception as e:
        error_msg = f"Failed to evaluate scores: {str(e)}"
        log_error("evaluate_all_scores", error_msg)
        return {"error": error_msg}


# ---------------------------------------------------------------------------
# Stale node aliases — kept so old imports don’t break during migration
# ---------------------------------------------------------------------------
evaluate_evidence  = evaluate_all_scores   # noqa: E305  (redirects to unified node)
evaluate_mechanism = evaluate_all_scores   # noqa
evaluate_proximity = evaluate_all_scores   # noqa



def calculate_rcps(state: RankingState) -> Dict[str, Any]:
    """
    Node 6: Calculate Root Cause Priority Score (RCPS) using configurable weights.
    Default: RCPS = 0.35×RPN_score + 0.30×Evidence + 0.20×Mechanism + 0.15×Proximity
    """
    log_node_start("calculate_rcps")
    
    try:
        proximity_evaluated = state.proximity_evaluated
        config = state.input.config or RankingConfig()
        weights = config.weights
        
        rcps_results = []
        
        for cause in proximity_evaluated:
            # Calculate RCPS with configurable weighted formula
            rcps = (
                weights.rpn_weight * cause["rpn_score"] +
                weights.evidence_weight * cause["evidence_strength"] +
                weights.mechanism_weight * cause["mechanism_fit"] +
                weights.proximity_weight * cause["causal_proximity"]
            )
            
            # Determine risk level (configurable thresholds could be added)
            if rcps >= 0.75:
                risk_level = "High"
            elif rcps >= 0.50:
                risk_level = "Medium"
            else:
                risk_level = "Low"
            
            result = {**cause, "rcps": rcps, "risk_level": risk_level}
            rcps_results.append(result)
            log_rcps_calculation(cause["cause_id"], rcps)
        
        log_node_end("calculate_rcps", f"Calculated RCPS for {len(rcps_results)} causes")
        return {"rcps_calculated": rcps_results}
        
    except Exception as e:
        error_msg = f"Failed to calculate RCPS: {str(e)}"
        log_error("calculate_rcps", error_msg)
        return {"error": error_msg}


def rank_and_format(state: RankingState) -> Dict[str, Any]:
    """
    Node 7: Rank causes by RCPS and format final output.
    """
    log_node_start("rank_and_format")
    
    try:
        rcps_calculated = state.rcps_calculated
        
        # Sort by RCPS descending
        sorted_causes = sorted(rcps_calculated, key=lambda x: x["rcps"], reverse=True)
        
        # Build ranked causes with justifications
        ranked_causes = []
        for rank, cause in enumerate(sorted_causes, start=1):
            justification = f"RPN: {cause['rpn']} (score: {cause['rpn_score']:.2f}), "
            justification += f"Evidence: {cause['evidence_strength']:.1f}, "
            justification += f"Mechanism: {cause['mechanism_fit']:.1f}, "
            justification += f"Proximity: {cause['causal_proximity']:.1f}"
            
            ranked_cause = RankedCause(
                rank=rank,
                cause_id=cause["cause_id"],
                cause_text=cause["cause_text"],
                rcps_score=round(cause["rcps"], 4),
                rpn=cause["rpn"],
                rpn_score=round(cause["rpn_score"], 4),
                evidence_strength=cause["evidence_strength"],
                mechanism_fit=cause["mechanism_fit"],
                causal_proximity=cause["causal_proximity"],
                risk_level=cause["risk_level"],
                justification=justification
            )
            ranked_causes.append(ranked_cause)
        
        # Create output with configuration context
        config = state.input.config or RankingConfig()
        top_cause = sorted_causes[0]
        
        output = RankingOutput(
            ranked_causes=ranked_causes,
            selected_root_cause=top_cause["cause_id"],
            total_causes=len(ranked_causes),
            domain=config.domain,
            config_used=config,
            message=f"Ranked {len(ranked_causes)} causes in {config.domain} domain. Top root cause: {top_cause['cause_id']} with RCPS {top_cause['rcps']:.4f}"
        )
        
        log_final_ranking(len(ranked_causes), top_cause["cause_id"])
        log_node_end("rank_and_format", f"Ranked {len(ranked_causes)} causes")
        
        return {"final_output": output}
        
    except Exception as e:
        error_msg = f"Failed to rank and format: {str(e)}"
        log_error("rank_and_format", error_msg)
        return {"error": error_msg}
