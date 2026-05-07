"""
Regulatory Agent
Main agent class that uses the LangGraph workflow.
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path

from .graph import create_regulatory_graph
from .state import AgentState
from .schemas import ComplaintInput, RegulatoryPolicy
from .logger import log_error, logger
from config.aws_bedrock_config import get_llm
from agent_ops import agentops_agent, agentops_operation


@agentops_agent(name="regulatory_agent")
class RegulatoryAgentLangGraph:
    """
    Regulatory Agent using LangGraph.
    Follows all best practices with modular architecture.
    Loads regulatory policy from JSON file.
    """
    
    def __init__(self, policy_path: Optional[str] = None):
        """
        Initialize the agent.
        
        Args:
            policy_path: Path to regulatory policy JSON file. 
                        If None, uses default regulatory_policy.json in same directory.
        """
        # Verify AWS Bedrock is available
        try:
            get_llm()
        except Exception as e:
            raise ValueError(f"AWS Bedrock initialization failed: {str(e)}")
        
        # Create graph
        self.graph = create_regulatory_graph()
        
        # Set policy path
        if policy_path is None:
            # Default to regulatory_policy.json in same directory
            current_dir = Path(__file__).parent
            self.policy_path = current_dir / "regulatory_policy.json"
        else:
            self.policy_path = Path(policy_path)
        
        # Load policy
        self.regulatory_policy = self._load_policy()
    
    def _load_policy(self) -> Optional[RegulatoryPolicy]:
        """
        Load regulatory policy from JSON file.
        
        Returns:
            RegulatoryPolicy object or None if file doesn't exist
        """
        try:
            if not self.policy_path.exists():
                log_error("policy_load", f"Policy file not found: {self.policy_path}")
                logger.info("Agent will return non-reportable for all complaints")
                return None
            
            with open(self.policy_path, 'r', encoding='utf-8') as f:
                policy_data = json.load(f)
            
            policy = RegulatoryPolicy(**policy_data)
            logger.info(f"Loaded {len(policy.regulatory_rules)} rules from {self.policy_path}")
            return policy
            
        except json.JSONDecodeError as e:
            log_error("policy_load", f"Invalid JSON in policy file: {str(e)}")
            return None
        except Exception as e:
            log_error("policy_load", f"Failed to load policy: {str(e)}")
            return None
    
    def reload_policy(self, policy_path: Optional[str] = None) -> bool:
        """
        Reload regulatory policy from file.
        
        Args:
            policy_path: Optional new path to policy file
            
        Returns:
            True if reload successful, False otherwise
        """
        if policy_path:
            self.policy_path = Path(policy_path)
        
        self.regulatory_policy = self._load_policy()
        return self.regulatory_policy is not None
    
    @agentops_operation(name="process_complaint")
    def process_complaint(
        self,
        complaint_data: ComplaintInput,
        policy_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process complaint and determine regulatory requirements.
        
        Args:
            complaint_data: Complaint information (only complaint_id, description, date_of_awareness required)
            policy_path: Optional path to regulatory policy JSON file. 
                        If provided, reloads policy from this path.
                        If None, uses the policy loaded during initialization.
            
        Returns:
            Dict with regulatory decision and metadata
        """
        # Reload policy if path provided
        if policy_path:
            logger.info(f"Reloading policy from: {policy_path}")
            self.reload_policy(policy_path)
        
        # Extract regulatory rules if policy exists
        regulatory_rules = None
        if self.regulatory_policy:
            regulatory_rules = [rule.dict() for rule in self.regulatory_policy.regulatory_rules]
            logger.info(f"Using {len(regulatory_rules)} regulatory rules")
        else:
            logger.info("No policy loaded - will return non-reportable")
        
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
