"""
Regulatory Agent Nodes
All node functions for the Regulatory Agent.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .state import AgentState
from .prompt import (
    JUSTIFICATION_SYSTEM_PROMPT,
    JUSTIFICATION_USER_PROMPT_TEMPLATE,
    NO_MATCH_JUSTIFICATION_PROMPT
)
from .logger import (
    log_node_entry,
    log_node_exit,
    log_routing_decision,
    log_error,
    log_rule_match,
    log_no_rule_match
)
from config.aws_bedrock_config import get_llm

# Use sentence-transformers for embeddings (open source)
try:
    from sentence_transformers import SentenceTransformer
    _embedding_model = None
    
    def get_embedding_model():
        """Lazy load embedding model"""
        global _embedding_model
        if _embedding_model is None:
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  # Small, fast, open source
        return _embedding_model
    
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    log_error("embeddings", "sentence-transformers not installed. Semantic matching disabled.")


def get_embedding(text: str) -> List[float]:
    """Get embedding vector for text using sentence-transformers"""
    if not EMBEDDINGS_AVAILABLE:
        return None
    
    try:
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        log_error("get_embedding", f"Embedding generation failed: {str(e)}")
        return None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def initialize_state_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state with defaults.
    Single responsibility: Set up initial state.
    """
    log_node_entry("initialize", state)
    
    updates = {
        "iteration": 0,
        "max_iterations": 5,
        "normalized_severity": None,
        "normalized_issue_type": None,
        "normalized_country": None,
        "matched_rules": None,
        "selected_rule": None,
        "regulatory_classification": None,
        "regulation_reference": None,
        "authority": None,
        "reportable": None,
        "report_type": None,
        "reporting_timeline_days": None,
        "timeline_type": None,
        "due_date": None,
        "capa_required": None,
        "compliance_risk_level": None,
        "matched_rule_id": None,
        "justification": None,
        "confidence": None,
        "error": None,
        "next_step": "normalize_input"
    }
    
    log_node_exit("initialize", updates)
    return updates


def normalize_input_node(state: AgentState) -> AgentState:
    """
    Node: Normalize input data.
    Single responsibility: Standardize fields if they exist.
    """
    log_node_entry("normalize_input", state)
    
    try:
        # Normalize severity (if exists)
        normalized_severity = None
        if state.get("severity"):
            severity_map = {
                "critical": "Critical",
                "major": "Major",
                "moderate": "Moderate",
                "minor": "Minor",
                "high": "Critical",
                "medium": "Moderate",
                "low": "Minor"
            }
            normalized_severity = severity_map.get(
                state.get("severity", "").lower(),
                state.get("severity")
            )
        
        # Normalize issue type (if exists)
        normalized_issue_type = None
        if state.get("issue_type"):
            issue_type_map = {
                "quality defect": "Quality Defect",
                "quality": "Quality Defect",
                "contamination": "Quality Defect",
                "packaging": "Packaging Defect",
                "labeling": "Labeling Error",
                "adverse event": "Adverse Event",
                "device malfunction": "Device Malfunction"
            }
            normalized_issue_type = issue_type_map.get(
                state.get("issue_type", "").lower(),
                state.get("issue_type")
            )
        
        # Normalize country (if exists)
        normalized_country = None
        if state.get("market_country"):
            country_map = {
                "usa": "USA",
                "us": "USA",
                "united states": "USA",
                "uk": "UK",
                "united kingdom": "UK",
                "eu": "EU",
                "europe": "EU"
            }
            normalized_country = country_map.get(
                state.get("market_country", "").lower(),
                state.get("market_country")
            )
        
        updates = {
            "normalized_severity": normalized_severity,
            "normalized_issue_type": normalized_issue_type,
            "normalized_country": normalized_country,
            "next_step": "evaluate_rules"
        }
        
        log_routing_decision("normalize_input", "evaluate_rules", "Normalization complete")
        log_node_exit("normalize_input", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Normalization failed: {str(e)}"
        log_error("normalize_input", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "no_match_fallback"
        }
        log_routing_decision("normalize_input", "no_match_fallback", "Exception occurred")
        log_node_exit("normalize_input", updates)
        return updates


def evaluate_rules_node(state: AgentState) -> AgentState:
    """
    Node: Evaluate complaint against regulatory rules.
    Single responsibility: Match complaint to applicable rules.
    """
    log_node_entry("evaluate_rules", state)
    
    try:
        regulatory_rules = state.get("regulatory_rules")
        
        if not regulatory_rules:
            log_no_rule_match(state.get("complaint_id", "unknown"))
            updates = {
                "next_step": "no_match_fallback"
            }
            log_routing_decision("evaluate_rules", "no_match_fallback", "No rules provided")
            log_node_exit("evaluate_rules", updates)
            return updates
        
        matched_rules = []
        
        for rule in regulatory_rules:
            if rule_matches_complaint(state, rule):
                matched_rules.append(rule)
                log_rule_match(rule.get("rule_id", "unknown"), state.get("complaint_id", "unknown"))
        
        if not matched_rules:
            log_no_rule_match(state.get("complaint_id", "unknown"))
            updates = {
                "matched_rules": [],
                "next_step": "no_match_fallback"
            }
            log_routing_decision("evaluate_rules", "no_match_fallback", "No rules matched")
            log_node_exit("evaluate_rules", updates)
            return updates
        
        updates = {
            "matched_rules": matched_rules,
            "next_step": "select_rule"
        }
        log_routing_decision("evaluate_rules", "select_rule", f"{len(matched_rules)} rules matched")
        log_node_exit("evaluate_rules", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Rule evaluation failed: {str(e)}"
        log_error("evaluate_rules", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "no_match_fallback"
        }
        log_routing_decision("evaluate_rules", "no_match_fallback", "Exception occurred")
        log_node_exit("evaluate_rules", updates)
        return updates


def rule_matches_complaint(state: AgentState, rule: Dict) -> bool:
    """
    Helper: Check if a rule matches the complaint.
    FULLY DYNAMIC - checks ANY condition field against complaint state.
    Uses embedding similarity for description_keywords if present.
    """
    conditions = rule.get("conditions", {})
    rule_id = rule.get("rule_id", "unknown")
    
    # Check country (special case - use normalized if available)
    rule_country = rule.get("country")
    if rule_country:
        complaint_country = state.get("normalized_country") or state.get("market_country")
        if complaint_country != rule_country:
            log_error("rule_match", f"Rule {rule_id}: Country mismatch - {complaint_country} != {rule_country}")
            return False
    
    # Check all conditions dynamically
    for condition_key, condition_value in conditions.items():
        
        # Special handling for description_keywords (semantic matching)
        if condition_key == "description_keywords":
            if isinstance(condition_value, str):
                complaint_embedding = get_embedding(state.get("description", ""))
                keywords_embedding = get_embedding(condition_value)
                
                if complaint_embedding and keywords_embedding:
                    similarity = cosine_similarity(complaint_embedding, keywords_embedding)
                    if similarity < 0.7:
                        log_error("rule_match", f"Rule {rule_id}: Description similarity too low - {similarity}")
                        return False
            continue
        
        # Get complaint value - try normalized first, then original
        complaint_value = None
        
        # Map to normalized fields if available
        if condition_key == "severity":
            complaint_value = state.get("normalized_severity") or state.get("severity")
        elif condition_key == "issue_type":
            complaint_value = state.get("normalized_issue_type") or state.get("issue_type")
        elif condition_key == "market_country" or condition_key == "country":
            complaint_value = state.get("normalized_country") or state.get("market_country")
        else:
            # For any other field, get directly from state
            complaint_value = state.get(condition_key)
        
        # If complaint doesn't have this field, rule doesn't match
        if complaint_value is None:
            log_error("rule_match", f"Rule {rule_id}: Field '{condition_key}' not found in complaint")
            return False
        
        # Check if condition value is a list (multiple acceptable values)
        if isinstance(condition_value, list):
            if complaint_value not in condition_value:
                log_error("rule_match", f"Rule {rule_id}: {condition_key}={complaint_value} not in {condition_value}")
                return False
        # Check if condition value is a boolean
        elif isinstance(condition_value, bool):
            if complaint_value != condition_value:
                log_error("rule_match", f"Rule {rule_id}: {condition_key}={complaint_value} != {condition_value}")
                return False
        # Check if condition value is a string or number (exact match)
        else:
            if complaint_value != condition_value:
                log_error("rule_match", f"Rule {rule_id}: {condition_key}={complaint_value} != {condition_value}")
                return False
    
    log_rule_match(rule_id, state.get("complaint_id", "unknown"))
    return True


def select_rule_node(state: AgentState) -> AgentState:
    """
    Node: Select the most appropriate rule from matched rules.
    Single responsibility: Choose highest priority rule.
    """
    log_node_entry("select_rule", state)
    
    try:
        matched_rules = state.get("matched_rules", [])
        
        # Priority: highest compliance_risk_level, then shortest timeline
        risk_priority = {"High": 3, "Medium": 2, "Low": 1}
        
        selected_rule = max(
            matched_rules,
            key=lambda r: (
                risk_priority.get(r.get("compliance_risk_level", "Low"), 0),
                -r.get("reporting_timeline_days", 999)
            )
        )
        
        updates = {
            "selected_rule": selected_rule,
            "next_step": "calculate_timeline"
        }
        log_routing_decision("select_rule", "calculate_timeline", f"Selected rule: {selected_rule.get('rule_id')}")
        log_node_exit("select_rule", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Rule selection failed: {str(e)}"
        log_error("select_rule", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "no_match_fallback"
        }
        log_routing_decision("select_rule", "no_match_fallback", "Exception occurred")
        log_node_exit("select_rule", updates)
        return updates


def calculate_timeline_node(state: AgentState) -> AgentState:
    """
    Node: Calculate reporting due date.
    Single responsibility: Compute due date based on timeline type.
    """
    log_node_entry("calculate_timeline", state)
    
    try:
        selected_rule = state.get("selected_rule", {})
        date_of_awareness = datetime.strptime(state.get("date_of_awareness", ""), "%Y-%m-%d")
        timeline_days = selected_rule.get("reporting_timeline_days", 0)
        timeline_type = selected_rule.get("timeline_type", "Calendar")
        
        if timeline_type == "Working":
            # Exclude weekends
            due_date = add_working_days(date_of_awareness, timeline_days)
        elif timeline_type == "Hours":
            # Add hours
            due_date = date_of_awareness + timedelta(hours=timeline_days)
        else:  # Calendar
            # Add calendar days
            due_date = date_of_awareness + timedelta(days=timeline_days)
        
        updates = {
            "due_date": due_date.strftime("%Y-%m-%d"),
            "next_step": "extract_decision"
        }
        log_routing_decision("calculate_timeline", "extract_decision", f"Due date: {updates['due_date']}")
        log_node_exit("calculate_timeline", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Timeline calculation failed: {str(e)}"
        log_error("calculate_timeline", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "no_match_fallback"
        }
        log_routing_decision("calculate_timeline", "no_match_fallback", "Exception occurred")
        log_node_exit("calculate_timeline", updates)
        return updates


def add_working_days(start_date: datetime, days: int) -> datetime:
    """
    Helper: Add working days (excluding weekends).
    """
    current_date = start_date
    days_added = 0
    
    while days_added < days:
        current_date += timedelta(days=1)
        # Skip weekends (5=Saturday, 6=Sunday)
        if current_date.weekday() < 5:
            days_added += 1
    
    return current_date


def extract_decision_node(state: AgentState) -> AgentState:
    """
    Node: Extract decision from selected rule.
    Single responsibility: Populate decision fields from rule.
    If multiple rules matched, combine all authorities.
    """
    log_node_entry("extract_decision", state)
    
    try:
        selected_rule = state.get("selected_rule", {})
        matched_rules = state.get("matched_rules", [selected_rule])
        
        # Collect all unique authorities from all matched rules
        all_authorities = []
        for rule in matched_rules:
            authorities = rule.get("authority", [])
            for auth in authorities:
                if auth not in all_authorities:
                    all_authorities.append(auth)
        
        updates = {
            "regulatory_classification": selected_rule.get("regulatory_classification"),
            "regulation_reference": selected_rule.get("regulation_reference"),
            "authority": all_authorities,  # All authorities from all matched rules
            "reportable": selected_rule.get("reportable", False),
            "report_type": selected_rule.get("report_type"),
            "reporting_timeline_days": selected_rule.get("reporting_timeline_days"),
            "timeline_type": selected_rule.get("timeline_type"),
            "capa_required": selected_rule.get("capa_required"),
            "compliance_risk_level": selected_rule.get("compliance_risk_level"),
            "matched_rule_id": selected_rule.get("rule_id"),
            "next_step": "generate_justification"
        }
        log_routing_decision("extract_decision", "generate_justification", "Decision extracted")
        log_node_exit("extract_decision", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Decision extraction failed: {str(e)}"
        log_error("extract_decision", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "no_match_fallback"
        }
        log_routing_decision("extract_decision", "no_match_fallback", "Exception occurred")
        log_node_exit("extract_decision", updates)
        return updates



def generate_justification_node(state: AgentState) -> AgentState:
    """
    Node: Generate justification using AWS Bedrock.
    Single responsibility: LLM-based explanation generation.
    """
    log_node_entry("generate_justification", state)
    
    try:
        # Get Bedrock LLM
        llm = get_llm()
        
        # Build matched conditions text
        selected_rule = state.get("selected_rule", {})
        conditions = selected_rule.get("conditions", {})
        matched_conditions = "\n".join([f"- {k}: {v}" for k, v in conditions.items()])
        
        # Build prompt
        user_prompt = JUSTIFICATION_USER_PROMPT_TEMPLATE.format(
            complaint_id=state.get("complaint_id", ""),
            product_type=state.get("product_type", ""),
            market_country=state.get("market_country", ""),
            severity=state.get("severity", ""),
            issue_type=state.get("issue_type", ""),
            description=state.get("description", ""),
            distributed_to_market=state.get("distributed_to_market", False),
            death_or_injury=state.get("death_or_injury", False),
            patient_risk_level=state.get("patient_risk_level", ""),
            rule_id=state.get("matched_rule_id", ""),
            regulation_reference=state.get("regulation_reference", ""),
            regulatory_classification=state.get("regulatory_classification", ""),
            reportable=state.get("reportable", False),
            authority=", ".join(state.get("authority", [])),
            report_type=state.get("report_type", ""),
            reporting_timeline_days=state.get("reporting_timeline_days", 0),
            timeline_type=state.get("timeline_type", ""),
            capa_required=state.get("capa_required", ""),
            compliance_risk_level=state.get("compliance_risk_level", ""),
            matched_conditions=matched_conditions
        )
        
        # Combine system and user prompt
        full_prompt = JUSTIFICATION_SYSTEM_PROMPT + "\n\n" + user_prompt
        
        # Call Bedrock
        response = llm.invoke(full_prompt)
        response_text = response.content.strip()
        
        # Clean and parse JSON
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        if '{' in response_text:
            response_text = response_text[response_text.index('{'):]
        if '}' in response_text:
            response_text = response_text[:response_text.rindex('}')+1]
        
        result = json.loads(response_text)
        
        updates = {
            "justification": result.get("justification", "Regulatory decision based on matched rule"),
            "confidence": result.get("confidence", 0.5),  # Use LLM confidence or default to neutral
            "next_step": "finalize"
        }
        log_routing_decision("generate_justification", "finalize", "Justification generated")
        log_node_exit("generate_justification", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Justification generation failed: {str(e)}"
        log_error("generate_justification", error_msg)
        # Fallback justification
        updates = {
            "justification": f"Regulatory decision based on {state.get('regulation_reference', 'matched rule')} for {state.get('regulatory_classification', 'regulatory requirement')}",
            "confidence": 0.5,  # Neutral confidence for fallback
            "next_step": "finalize"
        }
        log_routing_decision("generate_justification", "finalize", "Using fallback justification")
        log_node_exit("generate_justification", updates)
        return updates


def no_match_fallback_node(state: AgentState) -> AgentState:
    """
    Node: Handle cases where no rule matches.
    Single responsibility: Provide default non-reportable decision.
    """
    log_node_entry("no_match_fallback", state)
    
    try:
        # Get Bedrock LLM
        llm = get_llm()
        
        # Build prompt
        user_prompt = NO_MATCH_JUSTIFICATION_PROMPT.format(
            complaint_id=state.get("complaint_id", ""),
            product_type=state.get("product_type", ""),
            market_country=state.get("market_country", ""),
            severity=state.get("severity", ""),
            issue_type=state.get("issue_type", ""),
            description=state.get("description", ""),
            distributed_to_market=state.get("distributed_to_market", False),
            patient_risk_level=state.get("patient_risk_level", "")
        )
        
        # Combine system and user prompt
        full_prompt = JUSTIFICATION_SYSTEM_PROMPT + "\n\n" + user_prompt
        
        # Call Bedrock
        response = llm.invoke(full_prompt)
        response_text = response.content.strip()
        
        # Clean and parse JSON
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        if '{' in response_text:
            response_text = response_text[response_text.index('{'):]
        if '}' in response_text:
            response_text = response_text[:response_text.rindex('}')+1]
        
        result = json.loads(response_text)
        justification = result.get("justification", "No regulatory rule conditions satisfied.")
        confidence = result.get("confidence", 0.5)  # Use LLM confidence or neutral
        
    except Exception as e:
        log_error("no_match_fallback", f"Justification generation failed: {str(e)}")
        justification = "No regulatory rule conditions satisfied."
        confidence = 0.5  # Neutral confidence for error case
    
    updates = {
        "regulatory_classification": "Not Reportable",
        "regulation_reference": "N/A",
        "authority": [],
        "reportable": False,
        "report_type": "None",
        "reporting_timeline_days": 0,
        "timeline_type": "N/A",
        "due_date": "N/A",
        "capa_required": "No",
        "compliance_risk_level": "Low",
        "matched_rule_id": "None",
        "justification": justification,
        "confidence": confidence,
        "next_step": "finalize"
    }
    log_routing_decision("no_match_fallback", "finalize", "No match fallback applied")
    log_node_exit("no_match_fallback", updates)
    return updates


def finalize_node(state: AgentState) -> AgentState:
    """
    Node: Finalize output.
    Single responsibility: Prepare final response.
    """
    log_node_entry("finalize", state)
    
    updates = {
        "next_step": "end",
        "iteration": state.get("iteration", 0) + 1
    }
    
    log_routing_decision("finalize", "END", "Process complete")
    log_node_exit("finalize", updates)
    return updates
