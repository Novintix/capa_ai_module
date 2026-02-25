"""
Detection Agent API Router
Handles all detection-related endpoints
"""

import os
from fastapi import APIRouter, HTTPException

from .schemas import ComplaintData, DetectionScore
from .logger import log_api_request, log_api_response
from .agent import DetectionAgentLangGraph


# Create API router
router = APIRouter(prefix="/detection", tags=["detection"])

# Lazy initialization of detection agent
_detection_agent = None


def get_detection_agent():
    """Get or initialize the detection agent (lazy initialization)"""
    global _detection_agent
    if _detection_agent is None:
        _detection_agent = DetectionAgentLangGraph()
    return _detection_agent


@router.post("/", response_model=DetectionScore)
def detect_score(complaint: ComplaintData, policy_path: str = None):
    """
    Calculate detection score with optional policy document.
    
    If policy_path is provided, extracts rules from the policy document and uses LLM 
    to intelligently map the complaint to the appropriate policy rule.
    
    If policy_path is None, uses comprehensive default detection rules to intelligently
    understand and score the complaint.
    
    Args:
        complaint: Complaint data with source and description
        policy_path: Optional path to policy document (PDF, Word, Excel, or Image)
        
    Returns:
        DetectionScore with score, confidence, explanation, and decision_source
    """
    
    try:
        # Get detection agent (lazy initialization)
        detection_agent = get_detection_agent()
        
        # Log request
        log_api_request("/detection", complaint.complaint_id, has_policy=bool(policy_path))
        
        # Check if policy file exists (if provided)
        if policy_path and not os.path.exists(policy_path):
            raise HTTPException(
                status_code=404,
                detail=f"Policy document not found: {policy_path}"
            )
        
        # Process complaint with or without policy
        result = detection_agent.process_complaint(complaint, policy_document_path=policy_path)
        
        # Log response
        log_api_response(complaint.complaint_id, result["detection_score"], result["decision_source"])
        
        return DetectionScore(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating detection score: {str(e)}"
        )


@router.get("/health")
def detection_health():
    """Detection agent health check"""
    detection_agent = get_detection_agent()
    return {
        "status": "healthy",
        "agent": "detection",
        "google_api_key_present": bool(os.getenv("GOOGLE_API_KEY")),
        "azure_vision_key_present": bool(os.getenv("AZURE_VISION_KEY")),
        "detection_agent_initialized": detection_agent is not None
    }
