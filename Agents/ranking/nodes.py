"""
Node functions for Ranking Agent.
Each node performs a specific step in the RCPS calculation workflow.
"""

from typing import Dict, Any
from Agents.ranking.state import RankingState, RankedCause, RankingOutput, RankingConfig
from Agents.ranking.logger import (
    log_node_start, log_node_end, log_rpn_calculation,
    log_normalization, log_evidence_eval, log_mechanism_eval,
    log_proximity_eval, log_rcps_calculation, log_final_ranking, log_error
)
from Agents.ranking.prompts import (
    build_evidence_prompt,
    build_mechanism_prompt,
    build_proximity_prompt
)
from config.aws_bedrock_config import get_llm
import os


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


def evaluate_evidence(state: RankingState) -> Dict[str, Any]:
    """
    Node 3: Evaluate evidence strength using LLM.
    Evidence types: Observable (1.0), Indirect (0.7), Historical (0.5), None (0.3)
    """
    log_node_start("evaluate_evidence")
    
    try:
        rpn_normalized = state.rpn_normalized
        llm = get_llm()
        
        evidence_results = []
        
        for cause in rpn_normalized:
            config = state.input.config or RankingConfig()
            
            prompt = build_evidence_prompt(
                cause_text=cause['cause_text'],
                issue_type=cause['issue_type'],
                context_step=cause['context_step'],
                domain=config.domain,
                evidence_context=config.evidence_context
            )
            
            response = llm.invoke(prompt)
            score_text = response.content.strip()
            
            # Parse score with comprehensive validation
            try:
                evidence_score = float(score_text.strip())
                # Validate score is one of the allowed values
                allowed_scores = [1.0, 0.7, 0.5, 0.3]
                if evidence_score not in allowed_scores:
                    # Find closest allowed score
                    evidence_score = min(allowed_scores, key=lambda x: abs(x - evidence_score))
                    log_error("evaluate_evidence", f"LLM returned invalid score {score_text} for {cause['cause_id']}, using closest valid: {evidence_score}")
            except (ValueError, TypeError):
                # If LLM fails to return valid score, log error and use conservative default
                log_error("evaluate_evidence", f"Invalid LLM response for {cause['cause_id']}: '{score_text}'. Using default.")
                evidence_score = 0.5  # Conservative default (historical evidence level)
            
            # Additional validation - ensure score is reasonable
            if not (0.0 <= evidence_score <= 1.0):
                log_error("evaluate_evidence", f"Score out of range for {cause['cause_id']}: {evidence_score}. Clamping to valid range.")
                evidence_score = max(0.3, min(1.0, evidence_score))
            
            result = {**cause, "evidence_strength": evidence_score}
            evidence_results.append(result)
            log_evidence_eval(cause["cause_id"], evidence_score)
        
        log_node_end("evaluate_evidence", f"Evaluated evidence for {len(evidence_results)} causes")
        return {"evidence_evaluated": evidence_results}
        
    except Exception as e:
        error_msg = f"Failed to evaluate evidence: {str(e)}"
        log_error("evaluate_evidence", error_msg)
        return {"error": error_msg}



def evaluate_mechanism(state: RankingState) -> Dict[str, Any]:
    """
    Node 4: Evaluate mechanism fit using LLM.
    Scores: Strong (0.9), Moderate (0.7), Weak (0.4)
    """
    log_node_start("evaluate_mechanism")
    
    try:
        evidence_evaluated = state.evidence_evaluated
        llm = get_llm()
        
        mechanism_results = []
        
        for cause in evidence_evaluated:
            config = state.input.config or RankingConfig()
            
            prompt = build_mechanism_prompt(
                cause_text=cause['cause_text'],
                issue_type=cause['issue_type'],
                impact_description=cause['impact_description'],
                domain=config.domain,
                mechanism_context=config.mechanism_context
            )
            
            response = llm.invoke(prompt)
            score_text = response.content.strip()
            
            # Parse score with validation
            try:
                mechanism_score = float(score_text)
                # Validate score is one of the allowed values
                allowed_scores = [0.9, 0.7, 0.4]
                if mechanism_score not in allowed_scores:
                    # Find closest allowed score
                    mechanism_score = min(allowed_scores, key=lambda x: abs(x - mechanism_score))
            except (ValueError, TypeError):
                # If LLM fails to return valid score, log error and use conservative default
                log_error("evaluate_mechanism", f"Invalid LLM response for {cause['cause_id']}: '{score_text}'")
                mechanism_score = 0.7  # Conservative default (moderate fit)
            
            result = {**cause, "mechanism_fit": mechanism_score}
            mechanism_results.append(result)
            log_mechanism_eval(cause["cause_id"], mechanism_score)
        
        log_node_end("evaluate_mechanism", f"Evaluated mechanism for {len(mechanism_results)} causes")
        return {"mechanism_evaluated": mechanism_results}
        
    except Exception as e:
        error_msg = f"Failed to evaluate mechanism: {str(e)}"
        log_error("evaluate_mechanism", error_msg)
        return {"error": error_msg}


def evaluate_proximity(state: RankingState) -> Dict[str, Any]:
    """
    Node 5: Evaluate causal proximity using LLM.
    Scores: Direct (1.0), Contributor (0.7), Background (0.4)
    """
    log_node_start("evaluate_proximity")
    
    try:
        mechanism_evaluated = state.mechanism_evaluated
        llm = get_llm()
        
        proximity_results = []
        
        for cause in mechanism_evaluated:
            config = state.input.config or RankingConfig()
            
            prompt = build_proximity_prompt(
                cause_text=cause['cause_text'],
                issue_type=cause['issue_type'],
                context_step=cause['context_step'],
                domain=config.domain,
                proximity_context=config.proximity_context
            )
            
            response = llm.invoke(prompt)
            score_text = response.content.strip()
            
            # Parse score with validation
            try:
                proximity_score = float(score_text)
                # Validate score is one of the allowed values
                allowed_scores = [1.0, 0.7, 0.4]
                if proximity_score not in allowed_scores:
                    # Find closest allowed score
                    proximity_score = min(allowed_scores, key=lambda x: abs(x - proximity_score))
            except (ValueError, TypeError):
                # If LLM fails to return valid score, log error and use conservative default
                log_error("evaluate_proximity", f"Invalid LLM response for {cause['cause_id']}: '{score_text}'")
                proximity_score = 0.7  # Conservative default (contributor level)
            
            result = {**cause, "causal_proximity": proximity_score}
            proximity_results.append(result)
            log_proximity_eval(cause["cause_id"], proximity_score)
        
        log_node_end("evaluate_proximity", f"Evaluated proximity for {len(proximity_results)} causes")
        return {"proximity_evaluated": proximity_results}
        
    except Exception as e:
        error_msg = f"Failed to evaluate proximity: {str(e)}"
        log_error("evaluate_proximity", error_msg)
        return {"error": error_msg}



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
