"""
Zero Evidence Agent
Main agent class using the LangGraph workflow.

This agent is invoked when:
  - Validation agent has no evidence
  - No observable signals exist
  - No historical similar cases exist

It determines the Most Critical Functional Cause using
first-principles reasoning and composite criticality scoring.
"""

from typing import Dict, Any

from .graph import create_zero_evidence_graph
from .schemas import ZeroEvidenceInput
from .logger import log_error
from config.aws_bedrock_config import get_llm


class ZeroEvidenceAgent:
    """
    Zero Evidence Agent - Ranks causes by criticality and selects the most critical one.

    Simple flow:
    1. Receives list of causes
    2. LLM evaluates each cause (single-point failure, safety risk, safety blocking)
    3. Ranks by 5 criteria (severity, SPF, system dependency, safety impact, safety blocking)
    4. Returns the top-ranked cause
    """

    def __init__(self):
        """Initialize the Zero Evidence Agent."""
        # Verify AWS Bedrock is available
        try:
            get_llm()
        except Exception as e:
            raise ValueError(f"AWS Bedrock initialization failed: {str(e)}")

        # Create graph
        self.graph = create_zero_evidence_graph()

    def analyze(self, input_data: ZeroEvidenceInput) -> Dict[str, Any]:
        """
        Rank causes and return the most critical one.

        Args:
            input_data: Question and list of causes to rank

        Returns:
            {
                "selected_root_cause": {
                    "cause_id": "...",
                    "cause_text": "...",
                    "process_step": "...",
                    "reason": "..."
                },
                "confidence": 0.82
            }
        """
        try:
            # Validate input
            if not input_data.question_id or not input_data.question:
                return {
                    "selected_root_cause": None,
                    "confidence": 0.0,
                    "error": "Invalid input: question_id and question are required",
                }
            
            if not input_data.causes or len(input_data.causes) == 0:
                return {
                    "selected_root_cause": None,
                    "confidence": 0.0,
                    "error": "Invalid input: causes list cannot be empty",
                }
            
            # Build initial state
            causes_as_dicts = [cause.model_dump() for cause in input_data.causes]

            initial_state = {
                "question_id": input_data.question_id,
                "question": input_data.question,
                "causes": causes_as_dicts,
                "total_causes": input_data.total_causes,
                "llm_evaluations": None,
                "scored_causes": None,
                "selected_cause_id": None,
                "selected_cause_text": None,
                "selected_cause_process_step": None,
                "selection_reason": None,
                "confidence_level": None,
                "iteration": 0,
                "max_iterations": 5,
                "error": None,
                "next_step": None,
            }

            # Run graph
            final_state = self.graph.invoke(initial_state)

            # Check for errors
            if not final_state.get("selected_cause_id"):
                error_detail = final_state.get("error", "No cause selected")
                return {
                    "selected_root_cause": None,
                    "confidence": 0.0,
                    "error": error_detail,
                }

            # Return result
            return {
                "selected_root_cause": {
                    "cause_id": final_state["selected_cause_id"],
                    "cause_text": final_state["selected_cause_text"],
                    "process_step": final_state["selected_cause_process_step"],
                    "reason": final_state["selection_reason"],
                },
                "confidence": final_state.get("confidence_level", 0.5),
            }

        except ValueError as e:
            log_error("analyze", f"Validation error: {str(e)}")
            return {
                "selected_root_cause": None,
                "confidence": 0.0,
                "error": f"Validation error: {str(e)}",
            }
        except Exception as e:
            log_error("analyze", str(e))
            return {
                "selected_root_cause": None,
                "confidence": 0.0,
                "error": f"Agent error: {str(e)}",
            }
