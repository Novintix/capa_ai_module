"""
Regulatory Agent API Router
Handles all regulatory-related endpoints
"""

import os
from fastapi import APIRouter, HTTPException
from typing import Optional

from .schemas import ComplaintInput, RegulatoryPolicy, RegulatoryDecision
from .logger import log_api_request, log_api_response
from .agent import RegulatoryAgentLangGraph


# Create API router
router = APIRouter(prefix="/regulatory", tags=["regulatory"])

# Lazy initialization of regulatory agent
_regulatory_agent = None


def get_regulatory_agent():
    """Get or initialize the regulatory agent (lazy initialization)"""
    global _regulatory_agent
    if _regulatory_agent is None:
        _regulatory_agent = RegulatoryAgentLangGraph()
    return _regulatory_agent


@router.post("/", response_model=RegulatoryDecision)
def evaluate_regulatory_compliance(
    complaint: ComplaintInput,
    policy: Optional[RegulatoryPolicy] = None
):
    """
    Evaluate regulatory compliance and determine reporting requirements.
    
    Analyzes complaint against regulatory policy rules to determine:
    - Whether regulatory reporting is required
    - Which regulatory authority to report to
    - Reporting timeline and due date
    - CAPA requirements
    - Compliance risk level
    
    If policy is not provided, returns non-reportable decision with CAPA recommendation.
    
    Args:
        complaint: Complaint data with product and issue details
        policy: Optional regulatory policy with rules
        
    Returns:
        RegulatoryDecision with reportability, timeline, CAPA requirements, and justification
    """
    
    try:
        # Get regulatory agent (lazy initialization)
        regulatory_agent = get_regulatory_agent()
        
        # Log request
        log_api_request("/regulatory", complaint.complaint_id, has_policy=bool(policy))
        
        # Process complaint
        result = regulatory_agent.process_complaint(complaint, policy)
        
        # Log response
        log_api_response(
            complaint.complaint_id,
            result["reportable"],
            result["matched_rule_id"]
        )
        
        return RegulatoryDecision(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error evaluating regulatory compliance: {str(e)}"
        )


@router.get("/health")
def regulatory_health():
    """Regulatory agent health check"""
    # Check credentials without initializing agent
    aws_access_key_present = bool(os.getenv("AWS_ACCESS_KEY_ID"))
    aws_secret_key_present = bool(os.getenv("AWS_SECRET_ACCESS_KEY"))
    
    # Only try to initialize if credentials are present
    agent_initialized = False
    if aws_access_key_present and aws_secret_key_present:
        try:
            regulatory_agent = get_regulatory_agent()
            agent_initialized = regulatory_agent is not None
        except Exception as e:
            agent_initialized = False
    
    return {
        "status": "healthy" if (aws_access_key_present and aws_secret_key_present) else "degraded",
        "agent": "regulatory",
        "aws_access_key_present": aws_access_key_present,
        "aws_secret_key_present": aws_secret_key_present,
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        "regulatory_agent_initialized": agent_initialized
    }
