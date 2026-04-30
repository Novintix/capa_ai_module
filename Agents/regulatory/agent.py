"""
Regulatory Agent
Main agent class that uses the LangGraph workflow.
"""

from typing import Dict, Any, Optional

from .graph import create_regulatory_graph
from .state import AgentState
from .schemas import ComplaintInput, RegulatoryPolicy
from config.aws_bedrock_config import get_llm
from agent_ops import agentops_agent, agentops_operation


@agentops_agent(name="regulatory_agent")
class RegulatoryAgentLangGraph:
    """
    Regulatory Agent using LangGraph.
    Follows all best practices with modular architecture.
    """
    
    def __init__(self):
        """Initialize the agent."""
        # Verify AWS Bedrock is available
        try:
            get_llm()
        except Exception as e:
            raise ValueError(f"AWS Bedrock initialization failed: {str(e)}")
        
        # Create graph
        self.graph = create_regulatory_graph()
    
    @agentops_operation(name="process_complaint")
    def process_complaint(
        self,
        complaint_data: ComplaintInput,
        regulatory_policy: Optional[RegulatoryPolicy] = None
    ) -> Dict[str, Any]:
        """
        Process complaint and determine regulatory requirements.
        
        Args:
            complaint_data: Complaint information (only complaint_id, description, date_of_awareness required)
            regulatory_policy: Optional regulatory policy with rules
            
        Returns:
            Dict with regulatory decision and metadata
        """
        # Extract regulatory rules if policy provided
        regulatory_rules = None
        if regulatory_policy:
            regulatory_rules = [rule.dict() for rule in regulatory_policy.regulatory_rules]
        
        # Convert complaint to dict and handle optional fields
        complaint_dict = complaint_data.dict()
        
        # Initialize state with all complaint fields dynamically
        initial_state: AgentState = {
            "complaint_id": complaint_dict.get("complaint_id"),
            "product_type": complaint_dict.get("product_type"),
            "dosage_form": complaint_dict.get("dosage_form"),
            "market_country": complaint_dict.get("market_country"),
            "severity": complaint_dict.get("severity"),
            "issue_type": complaint_dict.get("issue_type"),
            "description": complaint_dict.get("description"),
            "distributed_to_market": complaint_dict.get("distributed_to_market"),
            "death_or_injury": complaint_dict.get("death_or_injury"),
            "patient_risk_level": complaint_dict.get("patient_risk_level"),
            "date_of_awareness": complaint_dict.get("date_of_awareness"),
            "regulatory_rules": regulatory_rules,
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
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
            "next_step": None
        }
        
        # Add any extra fields from complaint dynamically
        for key, value in complaint_dict.items():
            if key not in initial_state:
                initial_state[key] = value
        
        # Run graph
        final_state = self.graph.invoke(initial_state)
        
        # Return result
        return {
            "regulatory_classification": final_state["regulatory_classification"],
            "regulation_reference": final_state["regulation_reference"],
            "authority": final_state["authority"],
            "reportable": final_state["reportable"],
            "report_type": final_state["report_type"],
            "reporting_timeline_days": final_state["reporting_timeline_days"],
            "timeline_type": final_state["timeline_type"],
            "due_date": final_state["due_date"],
            "capa_required": final_state["capa_required"],
            "compliance_risk_level": final_state["compliance_risk_level"],
            "matched_rule_id": final_state["matched_rule_id"],
            "justification": final_state["justification"],
            "confidence": final_state["confidence"]
        }
