"""
Cause Generation Agent Nodes
All node functions for the Cause Generation Agent
"""

import os
import re
from typing import List, Dict, Any

from .state import AgentState
from .tools.excel_extractor import extract_fmea_from_excel, normalize_column_names
from .tools.semantic_matcher import rank_fmea_by_semantic_similarity
from .logger import (
    log_node_entry, log_node_exit, log_routing_decision, 
    log_error, log_fmea_parsing, log_matching, logger
)


def initialize_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state
    Single responsibility: Set up initial state
    """
    log_node_entry("initialize", state)
    
    updates = {
        "iteration": 0,
        "max_iterations": 5,
        "fmea_data": [],
        "matched_rows": [],
        "extracted_causes": [],
        "causes": [],
        "total_causes": 0,
        "matched_entries": 0,
        "confidence": 0.0,
        "error": None,
        "next_step": "validate_fmea"
    }
    
    log_node_exit("initialize", updates)
    return updates


def validate_fmea_node(state: AgentState) -> AgentState:
    """
    Node: Validate FMEA document exists
    Single responsibility: Check if FMEA file is accessible
    """
    log_node_entry("validate_fmea", state)
    
    fmea_path = state.get("fmea_document_path")
    
    if not fmea_path:
        error_msg = "FMEA document path not provided"
        log_error("validate_fmea", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_routing_decision("validate_fmea", "finalize", "No FMEA path")
        log_node_exit("validate_fmea", updates)
        return updates
    
    if not os.path.exists(fmea_path):
        error_msg = f"FMEA document not found: {fmea_path}"
        log_error("validate_fmea", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_routing_decision("validate_fmea", "finalize", "FMEA file not found")
        log_node_exit("validate_fmea", updates)
        return updates
    
    updates = {
        "next_step": "parse_fmea"
    }
    log_routing_decision("validate_fmea", "parse_fmea", "FMEA file exists")
    log_node_exit("validate_fmea", updates)
    return updates


def parse_fmea_node(state: AgentState) -> AgentState:
    """
    Node: Parse FMEA document
    Single responsibility: Extract structured data from FMEA Excel
    """
    log_node_entry("parse_fmea", state)
    
    try:
        fmea_path = state["fmea_document_path"]
        
        # Extract data from Excel
        fmea_data = extract_fmea_from_excel(fmea_path)
        
        # Normalize column names
        fmea_data = normalize_column_names(fmea_data)
        
        log_fmea_parsing(len(fmea_data))
        
        if not fmea_data:
            error_msg = "No data extracted from FMEA document"
            log_error("parse_fmea", error_msg)
            updates = {
                "error": error_msg,
                "next_step": "finalize"
            }
            log_routing_decision("parse_fmea", "finalize", "No data extracted")
            log_node_exit("parse_fmea", updates)
            return updates
        
        updates = {
            "fmea_data": fmea_data,
            "next_step": "parse_question"
        }
        log_routing_decision("parse_fmea", "parse_question", f"Parsed {len(fmea_data)} rows")
        log_node_exit("parse_fmea", {"next_step": "parse_question", "rows_parsed": len(fmea_data)})
        return updates
        
    except Exception as e:
        error_msg = f"FMEA parsing failed: {str(e)}"
        log_error("parse_fmea", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_routing_decision("parse_fmea", "finalize", "Exception occurred")
        log_node_exit("parse_fmea", updates)
        return updates


def parse_question_node(state: AgentState) -> AgentState:
    """
    Node: Parse question to extract keywords
    Single responsibility: Extract searchable terms from why question
    """
    log_node_entry("parse_question", state)
    
    try:
        question = state["question"].lower().strip()
        
        # Remove "why" and question marks
        question_clean = re.sub(r'\bwhy\b', '', question, flags=re.IGNORECASE)
        question_clean = question_clean.replace('?', '').strip()
        
        # Extract keywords (remove common words)
        stop_words = {'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'did', 'does', 'do'}
        keywords = [word for word in question_clean.split() if word not in stop_words and len(word) > 2]
        
        updates = {
            "question_keywords": keywords,
            "next_step": "match_fmea"
        }
        log_routing_decision("parse_question", "match_fmea", f"Extracted {len(keywords)} keywords")
        log_node_exit("parse_question", {"next_step": "match_fmea", "keywords": keywords})
        return updates
        
    except Exception as e:
        error_msg = f"Question parsing failed: {str(e)}"
        log_error("parse_question", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_routing_decision("parse_question", "finalize", "Exception occurred")
        log_node_exit("parse_question", updates)
        return updates


def match_fmea_node(state: AgentState) -> AgentState:
    """
    Node: Match question to FMEA entries using hybrid approach
    Single responsibility: Find all relevant FMEA rows using keywords + semantic similarity
    """
    log_node_entry("match_fmea", state)
    
    try:
        fmea_data = state["fmea_data"]
        keywords = state.get("question_keywords", [])
        question = state["question"]
        
        # Step 1: Keyword matching
        keyword_matched_rows = []
        
        for row in fmea_data:
            process_step = str(row.get("process_step", "")).lower()
            failure_mode = str(row.get("failure_mode", "")).lower()
            effects = str(row.get("effects", "")).lower()
            causes = str(row.get("causes", "")).lower()
            
            # Combine all searchable text
            searchable_text = f"{process_step} {failure_mode} {effects} {causes}"
            
            # Check if any keyword matches
            match_score = sum(1 for keyword in keywords if keyword in searchable_text)
            
            if match_score > 0:
                row["keyword_score"] = match_score
                keyword_matched_rows.append(row)
        
        # Step 2: Semantic matching (if keyword matching found results)
        if keyword_matched_rows:
            # Use semantic similarity to re-rank keyword matches
            try:
                semantic_ranked = rank_fmea_by_semantic_similarity(
                    question, 
                    keyword_matched_rows,
                    threshold=0.2  # Lower threshold since already keyword-filtered
                )
                matched_rows = semantic_ranked if semantic_ranked else keyword_matched_rows
                matching_method = "keyword + semantic"
            except Exception as e:
                # Fallback to keyword matching if semantic fails
                matched_rows = keyword_matched_rows
                matched_rows.sort(key=lambda x: x.get("keyword_score", 0), reverse=True)
                matching_method = "keyword only"
        else:
            # No keyword matches, try pure semantic matching
            try:
                semantic_ranked = rank_fmea_by_semantic_similarity(
                    question,
                    fmea_data,
                    threshold=0.4  # Higher threshold for pure semantic - be more selective
                )
                matched_rows = semantic_ranked
                matching_method = "semantic only"
            except Exception as e:
                # If semantic fails, return empty - don't return all
                matched_rows = []
                matching_method = "no match"
        
        log_matching(len(matched_rows))
        
        if not matched_rows:
            # NO FALLBACK - return empty if no match
            error_msg = "No FMEA entries matched the question. Try rephrasing or check FMEA document."
            log_error("match_fmea", error_msg)
            updates = {
                "error": error_msg,
                "matched_rows": [],
                "matched_entries": 0,
                "confidence": 0.0,
                "notes": "No matching FMEA entries found for the question.",
                "next_step": "finalize"
            }
            log_routing_decision("match_fmea", "finalize", "No matches found")
            log_node_exit("match_fmea", updates)
            return updates
        
        notes = f"Matched {len(matched_rows)} FMEA entries using {matching_method}"
        # Calculate confidence based on match quality
        if matching_method == "keyword + semantic":
            confidence = min(1.0, len(matched_rows) / 5.0 + 0.2)
        elif matching_method == "semantic only":
            confidence = min(1.0, len(matched_rows) / 5.0)
        else:
            confidence = 0.3
        
        updates = {
            "matched_rows": matched_rows,
            "matched_entries": len(matched_rows),
            "confidence": confidence,
            "notes": notes,
            "next_step": "extract_causes"
        }
        log_routing_decision("match_fmea", "extract_causes", f"Found {len(matched_rows)} matches")
        log_node_exit("match_fmea", {"next_step": "extract_causes", "matched_count": len(matched_rows), "method": matching_method})
        return updates
        
    except Exception as e:
        error_msg = f"FMEA matching failed: {str(e)}"
        log_error("match_fmea", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_routing_decision("match_fmea", "finalize", "Exception occurred")
        log_node_exit("match_fmea", updates)
        return updates


def extract_causes_node(state: AgentState) -> AgentState:
    """
    Node: Extract all causes from matched rows
    Single responsibility: Retrieve all documented FMEA causes
    """
    log_node_entry("extract_causes", state)
    
    try:
        matched_rows = state["matched_rows"]
        
        causes_list = []
        cause_counter = 1
        
        # Debug: Log first matched row structure
        if matched_rows:
            logger.info(f"[DEBUG] First matched row keys: {list(matched_rows[0].keys())}")
            logger.info(f"[DEBUG] First matched row sample: {dict(list(matched_rows[0].items())[:5])}")
        
        for idx, row in enumerate(matched_rows):
            # Try multiple possible column names for causes
            cause_text = (
                row.get("causes") or 
                row.get("potential_causes") or 
                row.get("cause") or
                row.get("potential_cause")
            )
            
            # Debug: Log what we found
            if idx < 3:  # Log first 3 rows
                logger.info(f"[DEBUG] Row {idx} - causes field: {cause_text}")
            
            if cause_text and str(cause_text).strip() and str(cause_text).lower() not in ['nan', 'what causes the step, change or feature to go wrong? (how could it occur?)']:
                # Skip header-like rows
                if 'what causes' in str(cause_text).lower() or 'how could it occur' in str(cause_text).lower():
                    continue
                
                # Safe integer conversion
                def safe_int(value):
                    if value is None:
                        return None
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return None
                
                cause_entry = {
                    "cause_id": f"C{cause_counter:03d}",
                    "cause_text": str(cause_text).strip(),
                    "process_step": str(row.get("process_step", "")).strip(),
                    "failure_mode": str(row.get("failure_mode", "")).strip(),
                    "potential_effects": str(row.get("effects", "")).strip() if row.get("effects") else None,
                    "severity": safe_int(row.get("severity")),
                    "occurrence": safe_int(row.get("occurrence")),
                    "detection": safe_int(row.get("detection")),
                    "current_controls": str(row.get("current_controls", "")).strip() if row.get("current_controls") else None,
                    "source": "FMEA"
                }
                causes_list.append(cause_entry)
                cause_counter += 1
        
        if not causes_list:
            error_msg = f"No causes found in {len(matched_rows)} matched FMEA rows. Check if 'Potential Causes' column has data."
            log_error("extract_causes", error_msg)
            updates = {
                "error": error_msg,
                "causes": [],
                "total_causes": 0,
                "next_step": "finalize"
            }
            log_routing_decision("extract_causes", "finalize", "No causes extracted")
            log_node_exit("extract_causes", updates)
            return updates
        
        updates = {
            "causes": causes_list,
            "total_causes": len(causes_list),
            "next_step": "finalize"
        }
        log_routing_decision("extract_causes", "finalize", f"Extracted {len(causes_list)} causes")
        log_node_exit("extract_causes", {"next_step": "finalize", "causes_count": len(causes_list)})
        return updates
        
    except Exception as e:
        error_msg = f"Cause extraction failed: {str(e)}"
        log_error("extract_causes", error_msg)
        updates = {
            "error": error_msg,
            "next_step": "finalize"
        }
        log_routing_decision("extract_causes", "finalize", "Exception occurred")
        log_node_exit("extract_causes", updates)
        return updates


def finalize_node(state: AgentState) -> AgentState:
    """
    Node: Finalize output
    Single responsibility: Prepare final response
    """
    log_node_entry("finalize", state)
    
    updates = {
        "next_step": "end",
        "iteration": state.get("iteration", 0) + 1
    }
    
    log_routing_decision("finalize", "END", "Process complete")
    log_node_exit("finalize", updates)
    return updates
