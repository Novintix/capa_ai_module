"""
Agent Nodes
All node functions for the Detection Agent.
"""

import os
import json
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import AgentState
from config.gemini_model_config import MODEL_NAME, TEMPERATURE, MAX_TOKENS, TIMEOUT, DEFAULT_SCORE_ON_ERROR
from .prompt import (
    POLICY_EXTRACTION_SYSTEM_PROMPT,
    POLICY_EXTRACTION_USER_PROMPT_TEMPLATE,
    DETECTION_SYSTEM_PROMPT,
    DETECTION_WITH_POLICY_USER_PROMPT_TEMPLATE,
    DETECTION_DEFAULT_USER_PROMPT_TEMPLATE
)
from .tools.pdf_extractor import extract_text_from_pdf
from .tools.word_extractor import extract_text_from_word
from .tools.excel_extractor import extract_text_from_excel
from .tools.ocr_extractor import extract_text_from_image
from .logger import log_node_entry, log_node_exit, log_routing_decision, log_error


def initialize_state_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state with defaults.
    Single responsibility: Set up initial state.
    """
    log_node_entry("initialize", state)
    
    updates = {
        "iteration": 0,
        "max_iterations": 5,
        "has_policy": state.get("policy_document_path") is not None,
        "policy_text": None,
        "policy_rules": None,
        "detection_score": None,
        "confidence": None,
        "rule_reference": None,
        "explanation": None,
        "decision_source": None,
        "error": None,
        "next_step": "check_policy"
    }
    
    log_node_exit("initialize", updates)
    return updates


def check_policy_node(state: AgentState) -> AgentState:
    """
    Node: Check if policy document exists.
    Single responsibility: Validate policy file.
    """
    log_node_entry("check_policy", state)
    
    policy_path = state.get("policy_document_path")
    
    if not policy_path:
        updates = {
            "has_policy": False,
            "next_step": "score_with_defaults"
        }
        log_routing_decision("check_policy", "score_with_defaults", "No policy path provided")
        log_node_exit("check_policy", updates)
        return updates
    
    if not os.path.exists(policy_path):
        error_msg = f"Policy file not found: {policy_path}"
        log_error("check_policy", error_msg)
        updates = {
            "has_policy": False,
            "error": error_msg,
            "next_step": "score_with_defaults"
        }
        log_routing_decision("check_policy", "score_with_defaults", "Policy file not found")
        log_node_exit("check_policy", updates)
        return updates
    
    updates = {
        "has_policy": True,
        "next_step": "extract_policy"
    }
    log_routing_decision("check_policy", "extract_policy", "Policy file exists")
    log_node_exit("check_policy", updates)
    return updates


def extract_policy_node(state: AgentState) -> AgentState:
    """
    Node: Extract text from policy document.
    Single responsibility: Document text extraction.
    """
    log_node_entry("extract_policy", state)
    
    try:
        policy_path = state["policy_document_path"]
        file_extension = Path(policy_path).suffix.lower()
        
        # Extract based on file type
        if file_extension == '.pdf':
            text = extract_text_from_pdf(policy_path)
        elif file_extension in ['.docx', '.doc']:
            text = extract_text_from_word(policy_path)
        elif file_extension in ['.xlsx', '.xls']:
            text = extract_text_from_excel(policy_path)
        elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp']:
            text = extract_text_from_image(policy_path)
        else:
            error_msg = f"Unsupported file type: {file_extension}"
            log_error("extract_policy", error_msg)
            updates = {
                "error": error_msg,
                "next_step": "score_with_defaults"
            }
            log_routing_decision("extract_policy", "score_with_defaults", "Unsupported file type")
            log_node_exit("extract_policy", updates)
            return updates
        
        if not text:
            error_msg = "No text extracted from policy document"
            log_error("extract_policy", error_msg)
            updates = {
                "error": error_msg,
                "next_step": "score_with_defaults"
            }
            log_routing_decision("extract_policy", "score_with_defaults", "No text extracted")
            log_node_exit("extract_policy", updates)
            return updates
        
        updates = {
            "policy_text": text,
            "next_step": "parse_policy"
        }
        log_routing_decision("extract_policy", "parse_policy", f"Extracted {len(text)} characters")
        log_node_exit("extract_policy", {"next_step": "parse_policy", "text_length": len(text)})
        return updates
        
    except Exception as e:
        error_msg = f"Policy extraction failed: {str(e)}"
        log_error("extract_policy", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "score_with_defaults"
        }
        log_routing_decision("extract_policy", "score_with_defaults", "Exception occurred")
        log_node_exit("extract_policy", updates)
        return updates


def parse_policy_node(state: AgentState) -> AgentState:
    """
    Node: Parse policy rules using LLM.
    Single responsibility: Extract structured rules from text.
    """
    log_node_entry("parse_policy", state)
    
    try:
        # Initialize LLM
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT
        )
        
        # Build prompt from template
        user_prompt = POLICY_EXTRACTION_USER_PROMPT_TEMPLATE.format(
            document_text=state["policy_text"]
        )
        
        messages = [
            SystemMessage(content=POLICY_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        # Call LLM
        response = llm.invoke(messages)
        response_text = response.content.strip()
        
        # Clean and parse JSON
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        if '{' in response_text:
            response_text = response_text[response_text.index('{'):]
        if '}' in response_text:
            response_text = response_text[:response_text.rindex('}')+1]
        
        policy_data = json.loads(response_text)
        rules = policy_data.get('detection_matrix', [])
        
        if not rules:
            error_msg = "No detection rules found in policy"
            log_error("parse_policy", error_msg)
            updates = {
                "error": error_msg,
                "next_step": "score_with_defaults"
            }
            log_routing_decision("parse_policy", "score_with_defaults", "No rules found")
            log_node_exit("parse_policy", updates)
            return updates
        
        updates = {
            "policy_rules": rules,
            "next_step": "score_with_policy"
        }
        log_routing_decision("parse_policy", "score_with_policy", f"Extracted {len(rules)} rules")
        log_node_exit("parse_policy", {"next_step": "score_with_policy", "rules_count": len(rules)})
        return updates
        
    except Exception as e:
        error_msg = f"Policy parsing failed: {str(e)}"
        log_error("parse_policy", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "score_with_defaults"
        }
        log_routing_decision("parse_policy", "score_with_defaults", "Exception occurred")
        log_node_exit("parse_policy", updates)
        return updates


def score_with_policy_node(state: AgentState) -> AgentState:
    """
    Node: Calculate score using policy rules.
    Single responsibility: LLM-based scoring with policy.
    """
    log_node_entry("score_with_policy", state)
    
    try:
        # Initialize LLM
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT
        )
        
        # Build policy rules text
        policy_rules_text = ""
        for idx, rule in enumerate(state["policy_rules"], 1):
            score = rule.get('score', 'N/A')
            description = rule.get('description', 'N/A')
            keywords = rule.get('keywords', [])
            
            policy_rules_text += f"{idx}. Score {score}: {description}\n"
            if keywords:
                policy_rules_text += f"   Keywords: {', '.join(keywords)}\n"
        
        # Build prompt from template
        user_prompt = DETECTION_WITH_POLICY_USER_PROMPT_TEMPLATE.format(
            complaint_source=state["complaint_source"],
            complaint_description=state["complaint_description"],
            policy_rules_text=policy_rules_text
        )
        
        messages = [
            SystemMessage(content=DETECTION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        # Call LLM
        response = llm.invoke(messages)
        response_text = response.content.strip()
        
        # Clean and parse JSON
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        if '{' in response_text:
            response_text = response_text[response_text.index('{'):]
        if '}' in response_text:
            response_text = response_text[:response_text.rindex('}')+1]
        
        result = json.loads(response_text)
        
        # Check for insufficient_data error
        if "error_type" in result:
            error_msg = result.get("error_message", "Insufficient data")
            log_error("score_with_policy", error_msg)
            updates = {
                "error": error_msg,
                "next_step": "score_with_defaults"
            }
            log_routing_decision("score_with_policy", "score_with_defaults", "Insufficient data")
            log_node_exit("score_with_policy", updates)
            return updates
        
        updates = {
            "detection_score": result.get("detection_score"),
            "confidence": result.get("confidence"),
            "rule_reference": result.get("rule_reference"),
            "explanation": result.get("explanation"),
            "decision_source": "policy",
            "next_step": "finalize"
        }
        log_routing_decision("score_with_policy", "finalize", f"Score: {updates['detection_score']}")
        log_node_exit("score_with_policy", {k: v for k, v in updates.items() if k != 'explanation'})
        return updates
        
    except Exception as e:
        error_msg = f"Scoring with policy failed: {str(e)}"
        log_error("score_with_policy", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "score_with_defaults"
        }
        log_routing_decision("score_with_policy", "score_with_defaults", "Exception occurred")
        log_node_exit("score_with_policy", updates)
        return updates


def score_with_defaults_node(state: AgentState) -> AgentState:
    """
    Node: Calculate score using default FMEA rules.
    Single responsibility: LLM-based scoring with defaults.
    """
    log_node_entry("score_with_defaults", state)
    
    try:
        # Initialize LLM
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT
        )
        
        # Build prompt from template
        user_prompt = DETECTION_DEFAULT_USER_PROMPT_TEMPLATE.format(
            complaint_source=state["complaint_source"],
            complaint_description=state["complaint_description"]
        )
        
        messages = [
            SystemMessage(content=DETECTION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        # Call LLM
        response = llm.invoke(messages)
        response_text = response.content.strip()
        
        # Clean and parse JSON
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        if '{' in response_text:
            response_text = response_text[response_text.index('{'):]
        if '}' in response_text:
            response_text = response_text[:response_text.rindex('}')+1]
        
        result = json.loads(response_text)
        
        updates = {
            "detection_score": result.get("detection_score", DEFAULT_SCORE_ON_ERROR),
            "confidence": result.get("confidence", 0.5),
            "rule_reference": result.get("rule_reference", "Default FMEA Rules"),
            "explanation": result.get("explanation", "Scored using default rules"),
            "decision_source": "default_rules",
            "next_step": "finalize"
        }
        log_routing_decision("score_with_defaults", "finalize", f"Score: {updates['detection_score']}")
        log_node_exit("score_with_defaults", {k: v for k, v in updates.items() if k != 'explanation'})
        return updates
        
    except Exception as e:
        error_msg = f"Scoring with defaults failed: {str(e)}"
        log_error("score_with_defaults", error_msg)
        updates = {
            "detection_score": DEFAULT_SCORE_ON_ERROR,
            "confidence": 0.0,
            "rule_reference": "Error Fallback",
            "explanation": f"Error: {str(e)}",
            "decision_source": "error",
            "next_step": "finalize"
        }
        log_routing_decision("score_with_defaults", "finalize", "Error fallback")
        log_node_exit("score_with_defaults", updates)
        return updates


def finalize_node(state: AgentState) -> AgentState:
    """
    Node: Finalize output.
    Single responsibility: Prepare final response.
    """
    log_node_entry("finalize", state)
    
    updates = {
        "next_step": "end",
        "iteration": state["iteration"] + 1
    }
    
    log_routing_decision("finalize", "END", "Process complete")
    log_node_exit("finalize", updates)
    return updates
