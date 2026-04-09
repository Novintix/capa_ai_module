"""
Cause Generation Agent
Main agent class for generating causes from FMEA documents
"""

from typing import Dict, Any

from .graph import create_cause_generation_graph
from .schemas import QuestionInput, CauseGenerationResult
from .logger import log_error


class CauseGenerationAgent:
    """
    Cause Generation Agent using LangGraph
    
    Responsibilities:
    - Parse FMEA documents
    - Match "why" questions to FMEA entries
    - Extract all documented causes
    - Return structured cause list
    
    Does NOT:
    - Rank causes
    - Validate causes
    - Calculate occurrence/detection/RPN
    - Use historical data for weighting
    """
    
    def __init__(self):
        """Initialize the cause generation agent"""
        self.graph = create_cause_generation_graph()
    
    def process_question(
        self, 
        question_input: QuestionInput, 
        fmea_document_path: str = None
    ) -> Dict[str, Any]:
        """
        Process why question and generate list of causes
        
        Args:
            question_input: Question input data (e.g., "Why did the bike stop?")
            fmea_document_path: Optional path to FMEA Excel document
            
        Returns:
            Dictionary with list of all possible causes
        """
        
        try:
            # Validate input (Pydantic should have already validated, but double-check)
            if not question_input.question_id or not question_input.question:
                return {
                    "question_id": question_input.question_id or "UNKNOWN",
                    "question": question_input.question or "",
                    "causes": [],
                    "total_causes": 0,
                    "fmea_document_used": fmea_document_path or "Not Available",
                    "matched_entries": 0,
                    "confidence": 0.0,
                    "notes": "Error: Invalid input - question_id and question are required"
                }
            
            # Prepare initial state
            initial_state = {
                "question_id": question_input.question_id,
                "question": question_input.question,
                "context": question_input.context,
                "fmea_document_path": fmea_document_path,
                "evidence_context": question_input.evidence_context if hasattr(question_input, 'evidence_context') else {}
            }
            
            # Run graph
            final_state = self.graph.invoke(initial_state)
            
            # Check for errors
            if final_state.get("error"):
                return {
                    "question_id": question_input.question_id,
                    "question": question_input.question,
                    "causes": [],
                    "total_causes": 0,
                    "fmea_document_used": final_state.get("fmea_document_used", fmea_document_path or "Not Available"),
                    "matched_entries": 0,
                    "confidence": 0.0,
                    "notes": f"Error: {final_state['error']}"
                }
            
            # Build result
            result = {
                "question_id": final_state.get("question_id"),
                "question": final_state.get("question"),
                "causes": final_state.get("causes", []),
                "total_causes": final_state.get("total_causes", 0),
                "fmea_document_used": final_state.get("fmea_document_used", fmea_document_path or "Not Available"),
                "matched_entries": final_state.get("matched_entries", 0),
                "evidence_extracted": final_state.get("evidence_extracted", 0),
                "confidence": final_state.get("confidence", 0.0),
                "notes": final_state.get("notes")
            }
            
            return result
            
        except ValueError as e:
            # Pydantic validation error
            log_error("process_question", f"Validation error: {str(e)}")
            return {
                "question_id": getattr(question_input, 'question_id', 'UNKNOWN'),
                "question": getattr(question_input, 'question', ''),
                "causes": [],
                "total_causes": 0,
                "fmea_document_used": fmea_document_path or "Not Available",
                "matched_entries": 0,
                "confidence": 0.0,
                "notes": f"Validation error: {str(e)}"
            }
        except Exception as e:
            log_error("process_question", str(e))
            return {
                "question_id": getattr(question_input, 'question_id', 'UNKNOWN'),
                "question": getattr(question_input, 'question', ''),
                "causes": [],
                "total_causes": 0,
                "fmea_document_used": fmea_document_path or "Not Available",
                "matched_entries": 0,
                "confidence": 0.0,
                "notes": f"Agent error: {str(e)}"
            }
