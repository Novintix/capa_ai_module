"""
Detection Agent
Main agent class that uses the LangGraph workflow.
"""

import os
from typing import Dict, Any, Optional

from detection.graph import create_detection_graph
from detection.state import AgentState
from detection.schemas import ComplaintData


class DetectionAgentLangGraph:
    """
    Detection Agent using LangGraph.
    Follows all best practices with modular architecture.
    """
    
    def __init__(self):
        """Initialize the agent."""
        # Verify API key
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        # Create graph
        self.graph = create_detection_graph()
    
    def process_complaint(
        self,
        complaint_data: ComplaintData,
        policy_document_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process complaint and calculate detection score.
        
        Args:
            complaint_data: Complaint information
            policy_document_path: Optional path to policy document
            
        Returns:
            Dict with detection score and metadata
        """
        # Initialize state
        initial_state: AgentState = {
            "complaint_id": complaint_data.complaint_id,
            "complaint_source": complaint_data.source,
            "complaint_description": complaint_data.description,
            "policy_document_path": policy_document_path,
            "policy_text": None,
            "policy_rules": None,
            "has_policy": False,
            "detection_score": None,
            "confidence": None,
            "rule_reference": None,
            "explanation": None,
            "decision_source": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
            "next_step": None
        }
        
        # Run graph
        final_state = self.graph.invoke(initial_state)
        
        # Return result
        return {
            "detection_score": final_state["detection_score"],
            "confidence": final_state["confidence"],
            "rule_reference": final_state["rule_reference"],
            "explanation": final_state["explanation"],
            "decision_source": final_state["decision_source"]
        }
