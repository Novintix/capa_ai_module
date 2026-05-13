"""
Cause Generation Agent Nodes
All node functions for the Cause Generation Agent
"""

import os
import re
import json
from typing import List, Dict, Any

from .state import AgentState
from .tools.excel_extractor import extract_fmea_from_excel, normalize_column_names
from .tools.semantic_matcher import rank_fmea_by_semantic_similarity
from .prompts import (
    get_unified_cause_messages,
    format_causes_for_validation,
    validate_prompt_inputs,
    get_scoring_prompt
)
from .logger import (
    log_node_entry, log_node_exit, log_routing_decision, 
    log_error, log_fmea_parsing, log_matching, logger
)
from config.aws_bedrock_config import get_llm


def initialize_node(state: AgentState) -> AgentState:
    """
    Node: Initialize state with input validation
    Single responsibility: Set up initial state and validate inputs
    """
    log_node_entry("initialize", state)
    
    # Validate required inputs
    question = state.get("question", "").strip()
    
    if not question:
        error_msg = "Invalid input: 'question' is required and cannot be empty"
        log_error("initialize", error_msg)
        updates = {
            "error": error_msg,
            "causes": [],
            "total_causes": 0,
            "confidence": 0.0,
            "next_step": "finalize"
        }
        log_routing_decision("initialize", "finalize", "Invalid question input")
        log_node_exit("initialize", updates)
        return updates
    
    # Validate question format (should be a "why" question or at least meaningful)
    if len(question) < 5:
        error_msg = f"Invalid input: Question too short (minimum 5 characters). Received: '{question}'"
        log_error("initialize", error_msg)
        updates = {
            "error": error_msg,
            "causes": [],
            "total_causes": 0,
            "confidence": 0.0,
            "next_step": "finalize"
        }
        log_routing_decision("initialize", "finalize", "Question too short")
        log_node_exit("initialize", updates)
        return updates
    
    # Validate question_id
    question_id = state.get("question_id", "").strip()
    if not question_id:
        error_msg = "Invalid input: 'question_id' is required and cannot be empty"
        log_error("initialize", error_msg)
        updates = {
            "error": error_msg,
            "causes": [],
            "total_causes": 0,
            "confidence": 0.0,
            "next_step": "finalize"
        }
        log_routing_decision("initialize", "finalize", "Invalid question_id")
        log_node_exit("initialize", updates)
        return updates
    
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
        # No FMEA path provided - this is OK, route to LLM generation
        updates = {
            "fmea_available": False,
            "next_step": "process_with_llm"
        }
        log_routing_decision("validate_fmea", "process_with_llm", "No FMEA path - will generate causes")
        log_node_exit("validate_fmea", updates)
        return updates
    
    if not os.path.exists(fmea_path):
        # FMEA path provided but file doesn't exist - route to LLM generation
        updates = {
            "fmea_available": False,
            "next_step": "process_with_llm"
        }
        log_routing_decision("validate_fmea", "process_with_llm", "FMEA file not found - will generate causes")
        log_node_exit("validate_fmea", updates)
        return updates
    
    updates = {
        "fmea_available": True,
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
        
        # Extract keywords (remove common words but keep important technical terms)
        stop_words = {'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'did', 'does', 'do', 'was', 'were', 'been', 'be', 'have', 'has', 'had'}
        
        # Split into words
        words = question_clean.split()
        
        # Extract single keywords
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Also extract 2-word and 3-word phrases for better matching
        for i in range(len(words) - 1):
            if words[i] not in stop_words or words[i+1] not in stop_words:
                bigram = f"{words[i]} {words[i+1]}"
                if len(bigram) > 5:  # Avoid very short phrases
                    keywords.append(bigram)
        
        for i in range(len(words) - 2):
            if any(word not in stop_words for word in [words[i], words[i+1], words[i+2]]):
                trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
                if len(trigram) > 8:  # Avoid very short phrases
                    keywords.append(trigram)
        
        updates = {
            "question_keywords": keywords,
            "next_step": "extract_from_evidence"
        }
        log_routing_decision("parse_question", "extract_from_evidence", f"Extracted {len(keywords)} keywords")
        log_node_exit("parse_question", {"next_step": "extract_from_evidence", "keywords": keywords})
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


def extract_from_evidence_node(state: AgentState) -> AgentState:
    """
    Node: Extract causes directly mentioned in evidence, logs, and reports
    Single responsibility: Find explicit cause mentions in evidence before FMEA matching
    
    This helps identify causes that are directly stated in investigation records,
    which will have high validation confidence later.
    """
    log_node_entry("extract_from_evidence", state)
    
    try:
        evidence_context = state.get("evidence_context", {})
        question = state.get("question", "").lower()
        
        # Debug logging
        logger.info(f"[extract_from_evidence] evidence_context keys: {list(evidence_context.keys()) if evidence_context else 'None'}")
        logger.info(f"[extract_from_evidence] evidence_context type: {type(evidence_context)}")
        if evidence_context:
            logger.info(f"[extract_from_evidence] evidence: {evidence_context.get('evidence', 'None')[:100] if evidence_context.get('evidence') else 'None'}")
            logger.info(f"[extract_from_evidence] logs count: {len(evidence_context.get('logs', []))}")
            logger.info(f"[extract_from_evidence] reports count: {len(evidence_context.get('reports', []))}")
        
        # Skip if no evidence context provided
        if not evidence_context:
            updates = {"evidence_extracted_causes": [], "next_step": "match_fmea"}
            log_routing_decision("extract_from_evidence", "match_fmea", "No evidence context provided")
            log_node_exit("extract_from_evidence", updates)
            return updates
        
        # Collect all evidence text
        evidence_texts = []
        
        # Add main evidence
        if evidence_context.get("evidence"):
            evidence_texts.append(("evidence", evidence_context["evidence"]))
        
        # Add logs
        for log_entry in evidence_context.get("logs", []):
            if isinstance(log_entry, dict) and log_entry.get("message"):
                evidence_texts.append(("log", log_entry["message"]))
        
        # Add reports
        for report in evidence_context.get("reports", []):
            if isinstance(report, dict) and report.get("summary"):
                evidence_texts.append(("report", report["summary"]))
        
        # Add investigation records
        for inv_record in evidence_context.get("investigation_records", []):
            if isinstance(inv_record, dict) and inv_record.get("note"):
                evidence_texts.append(("investigation", inv_record["note"]))
        
        # Add historical CAPA
        if evidence_context.get("historical_capa"):
            evidence_texts.append(("historical_capa", evidence_context["historical_capa"]))
        
        # Extract causes using LLM
        if evidence_texts:
            llm = get_llm()
            
            # Build evidence summary
            evidence_summary = "\n\n".join([f"[{source.upper()}]: {text}" for source, text in evidence_texts])
            
            prompt = f"""Extract any ROOT CAUSES or CONTRIBUTING FACTORS explicitly mentioned in the evidence below.

QUESTION: {state.get('question', '')}

EVIDENCE:
{evidence_summary}

INSTRUCTIONS:
1. Look for explicit mentions of causes, reasons, or contributing factors
2. Extract ONLY causes that are directly stated or strongly implied
3. Do NOT infer or speculate - only extract what's explicitly mentioned
4. For each cause, also describe the FAILURE MODE (the effect/consequence of this cause)
5. Return as JSON array with format: [{{"cause_text": "...", "failure_mode": "...", "source_reference": "evidence/log/report/investigation"}}]
6. If no explicit causes found, return empty array: []

CRITICAL FOR FAILURE_MODE:
- Describe what HAPPENS because of this cause (the effect/consequence)
- This will be used for the next "Why" question in iterative analysis
- Examples:
  * Cause: "Compression force set to 12 kN instead of 10 kN" → Failure Mode: "Excessive force applied to tablets"
  * Cause: "Calibration not performed" → Failure Mode: "Sensor readings inaccurate"
  * Cause: "Operator training inadequate" → Failure Mode: "Incorrect equipment setup"
- DO NOT use generic phrases like "Directly mentioned in evidence"

EXAMPLES OF WHAT TO EXTRACT:
- "Operator set compression force to 4.5 kN instead of 5.0 kN" → Extract with failure_mode: "Incorrect compression applied"
- "Calibration was skipped" → Extract with failure_mode: "Equipment not properly calibrated"
- "Historical CAPA identified X as root cause" → Extract with failure_mode describing the consequence

EXAMPLES OF WHAT NOT TO EXTRACT:
- General observations without cause attribution
- Symptoms or effects (not causes)
- Vague statements

Return ONLY the JSON array, no other text."""

            try:
                response = llm.invoke(prompt)
                response_text = response.content.strip()
                
                # Clean response
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                # Try to parse as array first
                extracted = None
                try:
                    # Look for array
                    start_idx = response_text.find('[')
                    end_idx = response_text.rfind(']')
                    
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        array_text = response_text[start_idx:end_idx+1]
                        extracted = json.loads(array_text)
                except:
                    pass
                
                # If not an array, try wrapping in array
                if extracted is None:
                    # Wrap in array brackets
                    if not response_text.startswith('['):
                        response_text = '[' + response_text + ']'
                    extracted = json.loads(response_text)
                
                # Convert to cause format (without hardcoded scores)
                evidence_causes = []
                for idx, item in enumerate(extracted, 1):
                    if isinstance(item, dict) and item.get("cause_text"):
                        evidence_causes.append({
                            "cause_id": f"E{idx:03d}",
                            "cause_text": item["cause_text"],
                            "process_step": "Evidence-based",
                            "failure_mode": item.get("failure_mode", "Evidence-based cause (effect to be determined)"),
                            "potential_effects": None,
                            "severity": None,  # Will be scored by LLM
                            "occurrence": None,  # Will be scored by LLM
                            "detection": None,  # Will be scored by LLM
                            "current_controls": None,
                            "source": f"Evidence ({item.get('source_reference', 'unknown')})"
                        })
                
                logger.info(f"[extract_from_evidence] Extracted {len(evidence_causes)} causes from evidence")
                
                updates = {
                    "evidence_extracted_causes": evidence_causes,
                    "next_step": "match_fmea"
                }
                log_routing_decision("extract_from_evidence", "match_fmea", f"Extracted {len(evidence_causes)} causes from evidence")
                log_node_exit("extract_from_evidence", {"causes_extracted": len(evidence_causes)})
                return updates
                
            except Exception as e:
                logger.warning(f"[extract_from_evidence] LLM extraction failed: {e}")
                # Log the response for debugging
                if 'response_text' in locals():
                    logger.warning(f"[extract_from_evidence] Full response: {response_text}")
                updates = {"evidence_extracted_causes": [], "next_step": "match_fmea"}
                log_routing_decision("extract_from_evidence", "match_fmea", "LLM extraction failed")
                log_node_exit("extract_from_evidence", updates)
                return updates
        else:
            updates = {"evidence_extracted_causes": [], "next_step": "match_fmea"}
            log_routing_decision("extract_from_evidence", "match_fmea", "No evidence texts found")
            log_node_exit("extract_from_evidence", updates)
            return updates
            
    except Exception as e:
        error_msg = f"Evidence extraction failed: {str(e)}"
        log_error("extract_from_evidence", error_msg)
        updates = {
            "evidence_extracted_causes": [],
            "next_step": "match_fmea"
        }
        log_routing_decision("extract_from_evidence", "match_fmea", "Exception occurred")
        log_node_exit("extract_from_evidence", updates)
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
                    threshold=0.1  # Very low threshold since already keyword-filtered
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
                    threshold=0.25  # Lower threshold for better semantic matching
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
                "fmea_document_used": state.get("fmea_document_path", "Unknown"),
                "next_step": "process_with_llm"
            }
            log_routing_decision("match_fmea", "process_with_llm", "No matches found")
            log_node_exit("match_fmea", updates)
            return updates
        
        notes = f"Matched {len(matched_rows)} FMEA entries using {matching_method}"
        # Calculate initial confidence based on match quality (will be refined in finalize)
        if matching_method == "keyword + semantic":
            confidence = min(1.0, len(matched_rows) / 5.0 + 0.2)
        elif matching_method == "semantic only":
            confidence = min(1.0, len(matched_rows) / 5.0)
        else:
            confidence = 0.3
        
        updates = {
            "matched_rows": matched_rows,
            "matched_entries": len(matched_rows),
            "confidence": confidence,  # Initial confidence, will be refined later
            "notes": notes,
            "fmea_document_used": state.get("fmea_document_path", "Unknown"),
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
    Node: Extract all causes from matched rows and combine with evidence-extracted causes
    Single responsibility: Retrieve all documented FMEA causes and merge with evidence causes
    """
    log_node_entry("extract_causes", state)
    
    try:
        matched_rows = state["matched_rows"]
        evidence_causes = state.get("evidence_extracted_causes", [])
        
        causes_list = []
        cause_counter = 1
        
        # First, add evidence-extracted causes (they have priority)
        for evidence_cause in evidence_causes:
            # Renumber to maintain sequence
            evidence_cause["cause_id"] = f"C{cause_counter:03d}"
            causes_list.append(evidence_cause)
            cause_counter += 1
        
        # Debug: Log first matched row structure
        if matched_rows:
            logger.info(f"[DEBUG] First matched row keys: {list(matched_rows[0].keys())}")
            logger.info(f"[DEBUG] First matched row sample: {dict(list(matched_rows[0].items())[:5])}")
        
        # Then add FMEA causes
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
                
                # Check for duplicates with evidence causes using semantic similarity
                cause_text_normalized = str(cause_text).strip().lower()
                is_duplicate = False
                
                # Simple keyword-based duplicate detection
                for existing in causes_list:
                    existing_text = existing["cause_text"].lower()
                    # Check if texts are very similar (>80% word overlap)
                    cause_words = set(cause_text_normalized.split())
                    existing_words = set(existing_text.split())
                    
                    if len(cause_words) > 0 and len(existing_words) > 0:
                        overlap = len(cause_words & existing_words)
                        similarity = overlap / max(len(cause_words), len(existing_words))
                        
                        if similarity > 0.8:  # 80% similarity threshold
                            is_duplicate = True
                            logger.info(f"[extract_causes] Skipping FMEA cause (duplicate of evidence): {cause_text[:60]}")
                            break
                
                if is_duplicate:
                    continue  # Skip duplicate
                
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
            error_msg = f"No causes found in {len(matched_rows)} matched FMEA rows and no evidence causes. Check if 'Potential Causes' column has data."
            log_error("extract_causes", error_msg)
            updates = {
                "error": error_msg,
                "causes": [],
                "total_causes": 0,
                "evidence_extracted": 0,
                "next_step": "process_with_llm"
            }
            log_routing_decision("extract_causes", "process_with_llm", "No causes extracted - will generate with LLM")
            log_node_exit("extract_causes", updates)
            return updates
        
        updates = {
            "causes": causes_list,
            "total_causes": len(causes_list),
            "evidence_extracted": len(evidence_causes),
            "next_step": "process_with_llm"
        }
        log_routing_decision("extract_causes", "process_with_llm", f"Extracted {len(causes_list)} causes ({len(evidence_causes)} from evidence, {len(causes_list) - len(evidence_causes)} from FMEA)")
        log_node_exit("extract_causes", {"next_step": "process_with_llm", "causes_count": len(causes_list), "evidence_count": len(evidence_causes)})
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
    Single responsibility: Prepare final response and calculate confidence
    """
    log_node_entry("finalize", state)
    
    # Calculate confidence based on scores and source
    causes = state.get("causes", [])
    confidence = state.get("confidence")
    
    if confidence is None and causes:
        # Calculate confidence based on:
        # 1. Source reliability (Evidence > FMEA > Generated)
        # 2. Score completeness
        # 3. Number of causes
        # 4. Average RPN (Risk Priority Number) - higher RPN = more confident in risk assessment
        
        evidence_count = sum(1 for c in causes if "Evidence" in c.get("source", ""))
        fmea_count = sum(1 for c in causes if c.get("source") == "FMEA")
        generated_count = sum(1 for c in causes if c.get("source") == "Generated")
        
        scored_count = sum(1 for c in causes if c.get("severity") and c.get("occurrence") and c.get("detection"))
        
        # Calculate average RPN for scored causes
        rpn_values = []
        for c in causes:
            if c.get("severity") and c.get("occurrence") and c.get("detection"):
                rpn = c["severity"] * c["occurrence"] * c["detection"]
                rpn_values.append(rpn)
        
        avg_rpn = sum(rpn_values) / len(rpn_values) if rpn_values else 0
        
        # Base confidence on source mix (dynamic based on actual counts)
        total_causes = len(causes)
        evidence_ratio = evidence_count / total_causes
        fmea_ratio = fmea_count / total_causes
        generated_ratio = generated_count / total_causes
        
        # Weighted confidence based on source reliability
        base_confidence = (
            evidence_ratio * 0.85 +    # Evidence-based: highest confidence
            fmea_ratio * 0.75 +         # FMEA: good confidence
            generated_ratio * 0.60      # Generated: moderate confidence
        )
        
        # Adjust for score completeness
        if scored_count == len(causes):
            score_factor = 1.0
        elif scored_count > 0:
            score_factor = 0.85
        else:
            score_factor = 0.70
        
        # Adjust for number of causes (more causes = slightly lower confidence per cause)
        if len(causes) <= 3:
            count_factor = 1.0
        elif len(causes) <= 5:
            count_factor = 0.95
        else:
            count_factor = 0.90
        
        # Adjust for RPN distribution (if we have high-risk causes, we're more confident)
        if avg_rpn > 200:  # High risk
            rpn_factor = 1.05
        elif avg_rpn > 100:  # Medium risk
            rpn_factor = 1.0
        else:  # Low risk
            rpn_factor = 0.95
        
        confidence = min(1.0, base_confidence * score_factor * count_factor * rpn_factor)
    elif confidence is None:
        confidence = 0.0
    
    updates = {
        "confidence": round(confidence, 2),
        "next_step": "end",
        "iteration": state.get("iteration", 0) + 1,
        "evidence_extracted": state.get("evidence_extracted", 0)
    }
    
    log_routing_decision("finalize", "END", "Process complete")
    log_node_exit("finalize", updates)
    return updates


def deduplicate_causes_node(state: AgentState) -> AgentState:
    """
    Node: Deduplicate causes using LLM
    Single responsibility: Remove duplicate/similar causes after all processing
    """
    log_node_entry("deduplicate_causes", state)
    
    causes = state.get("causes", [])
    
    if not causes or len(causes) <= 1:
        # No deduplication needed
        log_node_exit("deduplicate_causes", {"next_step": "score_causes", "causes_count": len(causes)})
        return {"next_step": "score_causes"}
    
    try:
        from .prompts import get_deduplication_prompt
        from config.aws_bedrock_config import get_llm
        
        # Build deduplication prompt
        prompt = get_deduplication_prompt(causes)
        
        # Call LLM with temperature=0 for deterministic results
        llm = get_llm()
        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            logger.warning("[deduplicate_causes] No JSON found in LLM response, keeping all causes")
            log_node_exit("deduplicate_causes", {"next_step": "score_causes", "deduplication": "skipped"})
            return {"next_step": "score_causes"}
        
        result = json.loads(json_match.group())
        
        unique_causes = result.get("unique_causes", [])
        removed_duplicates = result.get("removed_duplicates", [])
        
        if not unique_causes:
            logger.warning("[deduplicate_causes] No unique causes returned, keeping original causes")
            log_node_exit("deduplicate_causes", {"next_step": "score_causes", "deduplication": "failed"})
            return {"next_step": "score_causes"}
        
        logger.info(f"[deduplicate_causes] Deduplication complete:")
        logger.info(f"  - Input causes: {len(causes)}")
        logger.info(f"  - Unique causes: {len(unique_causes)}")
        logger.info(f"  - Removed duplicates: {len(removed_duplicates)}")
        
        for dup in removed_duplicates:
            logger.info(f"  - Removed {dup.get('removed_cause_id')}: {dup.get('reason')}")
        
        updates = {
            "causes": unique_causes,
            "total_causes": len(unique_causes),
            "removed_duplicates": removed_duplicates,
            "next_step": "score_causes"
        }
        
        log_routing_decision("deduplicate_causes", "score_causes", f"Deduplication complete: {len(causes)} -> {len(unique_causes)} causes")
        log_node_exit("deduplicate_causes", updates)
        return updates
        
    except Exception as e:
        error_msg = f"Deduplication failed: {str(e)}"
        logger.error(f"[deduplicate_causes] {error_msg}")
        log_error("deduplicate_causes", error_msg)
        # Continue with original causes if deduplication fails
        log_node_exit("deduplicate_causes", {"next_step": "score_causes", "error": error_msg})
        return {"next_step": "score_causes"}


def score_causes_node(state: AgentState) -> AgentState:
    """
    Node: Score causes with Severity, Occurrence, Detection using LLM
    Single responsibility: Assign risk scores to all causes based on context
    """
    log_node_entry("score_causes", state)
    
    try:
        causes = state.get("causes", [])
        
        if not causes:
            # No causes to score, skip to finalize
            updates = {"next_step": "finalize"}
            log_routing_decision("score_causes", "finalize", "No causes to score")
            log_node_exit("score_causes", updates)
            return updates
        
        # Check if any cause needs scoring
        needs_scoring = any(
            cause.get("severity") is None or 
            cause.get("occurrence") is None or 
            cause.get("detection") is None 
            for cause in causes
        )
        
        if not needs_scoring:
            # All causes already have scores, skip to finalize
            updates = {"next_step": "finalize"}
            log_routing_decision("score_causes", "finalize", "All causes already scored")
            log_node_exit("score_causes", updates)
            return updates
        
        # Get LLM to score causes
        question = state.get("question", "")
        evidence_context = state.get("evidence_context", {})
        
        llm = get_llm()
        prompt = get_scoring_prompt(question, causes, evidence_context)
        
        # Call LLM
        response = llm.invoke(prompt)
        response_text = response.content.strip()
        
        # Clean response
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Extract JSON array
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            array_text = response_text[start_idx:end_idx+1]
            scores = json.loads(array_text)
            
            # Apply scores to causes
            score_map = {score.get("cause_id"): score for score in scores}
            
            scored_count = 0
            for cause in causes:
                cause_id = cause.get("cause_id")
                if cause_id in score_map:
                    score_data = score_map[cause_id]
                    
                    # Update scores if they were None
                    if cause.get("severity") is None:
                        cause["severity"] = score_data.get("severity")
                    if cause.get("occurrence") is None:
                        cause["occurrence"] = score_data.get("occurrence")
                    if cause.get("detection") is None:
                        cause["detection"] = score_data.get("detection")
                    
                    scored_count += 1
            
            logger.info(f"[score_causes] Scored {scored_count}/{len(causes)} causes")
            
            updates = {
                "causes": causes,
                "next_step": "finalize"
            }
            log_routing_decision("score_causes", "finalize", f"Scored {scored_count} causes")
            log_node_exit("score_causes", {"scored_count": scored_count})
            return updates
        else:
            # Failed to parse scores, log warning and continue
            logger.warning(f"[score_causes] Failed to parse LLM scores, continuing with existing scores")
            updates = {"next_step": "finalize"}
            log_routing_decision("score_causes", "finalize", "Score parsing failed")
            log_node_exit("score_causes", updates)
            return updates
            
    except Exception as e:
        error_msg = f"Cause scoring failed: {str(e)}"
        log_error("score_causes", error_msg)
        logger.warning(f"[score_causes] {error_msg}, continuing with existing scores")
        
        # Don't fail the entire process, just continue
        updates = {"next_step": "finalize"}
        log_routing_decision("score_causes", "finalize", "Exception occurred")
        log_node_exit("score_causes", updates)
        return updates


def clean_llm_response(response_text: str) -> str:
    """Clean LLM response by removing reasoning tags and markdown"""
    # Strip reasoning tags if present
    if "<reasoning>" in response_text and "</reasoning>" in response_text:
        response_text = re.sub(r'<reasoning>.*?</reasoning>\s*', '', response_text, flags=re.DOTALL).strip()
    
    # Remove markdown code blocks
    response_text = response_text.replace('```json', '').replace('```', '').strip()
    
    # Extract JSON object - find first { and last }
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        response_text = response_text[start_idx:end_idx+1]
    else:
        raise ValueError(f"No valid JSON object found in response")
    
    return response_text


def process_with_llm_node(state: AgentState) -> AgentState:
    """
    Node: Process causes with LLM (validation or generation)
    Single responsibility: Either validate FMEA causes or generate causes when no FMEA
    """
    log_node_entry("process_with_llm", state)
    
    try:
        question = state["question"]
        complaint_description = state.get("context", "")
        causes = state.get("causes", [])
        fmea_available = state.get("fmea_available", False)
        
        # Validate inputs
        if not validate_prompt_inputs(question):
            error_msg = "Invalid question for LLM processing"
            log_error("process_with_llm", error_msg)
            updates = {
                "notes": f"LLM processing failed: {error_msg}",
                "next_step": "finalize"
            }
            log_routing_decision("process_with_llm", "finalize", "Invalid inputs")
            log_node_exit("process_with_llm", updates)
            return updates
        
        # Initialize LLM
        llm = get_llm()
        
        if fmea_available and causes:
            # VALIDATION MODE: Filter FMEA causes
            causes_text = format_causes_for_validation(causes)
            messages = get_unified_cause_messages(question, causes_text=causes_text)

            # Call LLM
            response = llm.invoke(messages)
            response_text = clean_llm_response(response.content)
            
            # Parse JSON response
            result = json.loads(response_text)
            
            if result.get("mode") == "validation":
                relevant_numbers = result.get("relevant_cause_numbers", [])
                reasoning = result.get("reasoning", "LLM validation applied")
                
                # Filter causes based on LLM validation
                filtered_causes = []
                for i, cause in enumerate(causes, 1):
                    if i in relevant_numbers:
                        filtered_causes.append(cause)
                
                # Update cause IDs to be sequential
                for i, cause in enumerate(filtered_causes, 1):
                    cause["cause_id"] = f"C{i:03d}"
                
                updates = {
                    "causes": filtered_causes,
                    "total_causes": len(filtered_causes),
                    "notes": f"LLM filtered {len(causes)} causes to {len(filtered_causes)} relevant causes. {reasoning}",
                    "next_step": "deduplicate_causes"
                }
                
                log_routing_decision("process_with_llm", "deduplicate_causes", f"Filtered to {len(filtered_causes)} relevant causes")
                log_node_exit("process_with_llm", {"next_step": "deduplicate_causes", "filtered_count": len(filtered_causes)})
                return updates
            else:
                # Unexpected response format, continue with unfiltered causes
                updates = {
                    "notes": "LLM validation returned unexpected format, returning all causes",
                    "next_step": "deduplicate_causes"
                }
                log_routing_decision("process_with_llm", "deduplicate_causes", "Unexpected LLM response")
                log_node_exit("process_with_llm", updates)
                return updates
                
        else:
            # GENERATION MODE: Generate causes when no FMEA or FMEA extraction failed
            messages = get_unified_cause_messages(question, complaint_description=complaint_description)

            # Call LLM
            response = llm.invoke(messages)
            response_text = clean_llm_response(response.content)
            
            # Parse JSON response
            result = json.loads(response_text)
            
            if result.get("mode") == "generation":
                generated_causes = result.get("causes", [])
                
                # Add cause IDs and ensure proper format
                for i, cause in enumerate(generated_causes, 1):
                    cause["cause_id"] = f"C{i:03d}"
                    if "source" not in cause:
                        cause["source"] = "Generated"
                
                updates = {
                    "causes": generated_causes,
                    "total_causes": len(generated_causes),
                    "matched_entries": 0,
                    "confidence": None,  # Will be calculated based on scores
                    "notes": "FMEA document not available. Generated possible causes using expert knowledge.",
                    "fmea_document_used": "Not Available",
                    "next_step": "deduplicate_causes"
                }
                
                log_routing_decision("process_with_llm", "deduplicate_causes", f"Generated {len(generated_causes)} causes")
                log_node_exit("process_with_llm", {"next_step": "deduplicate_causes", "generated_count": len(generated_causes)})
                return updates
            else:
                # Unexpected response format
                error_msg = "LLM generation returned unexpected format"
                log_error("process_with_llm", error_msg)
                updates = {
                    "causes": [],
                    "total_causes": 0,
                    "matched_entries": 0,
                    "confidence": 0.0,
                    "notes": f"Unable to generate causes: {error_msg}",
                    "fmea_document_used": "Not Available",
                    "error": error_msg,
                    "next_step": "finalize"
                }
                log_routing_decision("process_with_llm", "finalize", "LLM generation failed")
                log_node_exit("process_with_llm", updates)
                return updates
        
    except Exception as e:
        error_msg = f"LLM processing failed: {str(e)}"
        log_error("process_with_llm", error_msg)
        
        # Return appropriate fallback based on mode
        if state.get("fmea_available", False) and state.get("causes"):
            # Had FMEA causes, return them unfiltered
            updates = {
                "notes": f"LLM validation failed, returning all causes: {error_msg}",
                "next_step": "finalize"
            }
        else:
            # No FMEA, return empty
            updates = {
                "causes": [],
                "total_causes": 0,
                "matched_entries": 0,
                "confidence": 0.0,
                "notes": f"Unable to generate causes: {error_msg}",
                "fmea_document_used": "Not Available",
                "error": error_msg,
                "next_step": "finalize"
            }
        
        log_routing_decision("process_with_llm", "finalize", "LLM processing failed")
        log_node_exit("process_with_llm", updates)
        return updates
