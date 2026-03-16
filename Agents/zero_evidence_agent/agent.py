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
    Zero Evidence Agent using LangGraph.

    Responsibilities:
    - Accept cause list from cause generation agent
    - Use Bedrock LLM to evaluate single point failure and safety risk
    - Apply deterministic criticality scoring formula
    - Return exactly ONE most critical cause

    Does NOT:
    - Generate new causes
    - Use historical data
    - Validate against evidence
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
        Analyze candidate causes and return the Most Critical Functional Cause.

        Args:
            input_data: ZeroEvidenceInput containing question and list of causes

        Returns:
            Dict matching the ZeroEvidenceResult schema:
            {
                "mode": "ZERO_EVIDENCE_MODE",
                "selected_root_cause": {
                    "cause_id": "...",
                    "cause_text": "...",
                    "process_step": "...",
                    "reason": "..."
                },
                "confidence": "MEDIUM"
            }
        """
        try:
            # Build initial state — convert Pydantic models to plain dicts
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

            # Check for unrecoverable error (no cause selected)
            if not final_state.get("selected_cause_id"):
                error_detail = final_state.get("error", "Unknown error — no cause selected")
                return {
                    "mode": "ZERO_EVIDENCE_MODE",
                    "selected_root_cause": None,
                    "confidence": "LOW",
                    "error": error_detail,
                }

            # Build result
            return {
                "mode": "ZERO_EVIDENCE_MODE",
                "selected_root_cause": {
                    "cause_id": final_state["selected_cause_id"],
                    "cause_text": final_state["selected_cause_text"],
                    "process_step": final_state["selected_cause_process_step"],
                    "reason": final_state["selection_reason"],
                },
                "confidence": final_state.get("confidence_level", "MEDIUM"),
            }

        except Exception as e:
            log_error("analyze", str(e))
            return {
                "mode": "ZERO_EVIDENCE_MODE",
                "selected_root_cause": None,
                "confidence": "LOW",
                "error": f"Agent error: {str(e)}",
            }
