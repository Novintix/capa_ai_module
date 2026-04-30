"""
Pattern Agent API Router
Handles all pattern-related endpoints
"""

import os
from fastapi import APIRouter, HTTPException

from .schemas import PatternAnalysisRequest, PatternAnalysisResponse
from .agent import PatternAgentLangGraph
from .logger import log_api_request, log_api_response
from agent_ops import agentops_session


# Create API router
router = APIRouter(prefix="/pattern", tags=["pattern"])

# Lazy initialization of pattern agent
_pattern_agent = None


def get_pattern_agent():
    """Get or initialize the pattern agent (lazy initialization)"""
    global _pattern_agent
    if _pattern_agent is None:
        _pattern_agent = PatternAgentLangGraph()
    return _pattern_agent


@router.post("/", response_model=PatternAnalysisResponse)
@agentops_session(name="pattern@router.post(_, response_model=PatternAnalysisResponse)", tags=["agents", "pattern"])
def analyze_pattern(request: PatternAnalysisRequest):
    """
    Analyze patterns in historical complaint data for the given complaint input.
    """
    
    try:
        # Get pattern agent (lazy initialization)
        pattern_agent = get_pattern_agent()
        
        # Log request
        log_api_request("/pattern", request.complaint_id)
        
        # Process complaint
        result_dict = pattern_agent.process_pattern(request)
        
        # Log response
        log_api_response(request.complaint_id, result_dict.get("trend_score", 1))
        
        return PatternAnalysisResponse(**result_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing pattern: {str(e)}"
        )


@router.get("/health")
def pattern_health():
    """Pattern agent health check"""
    pattern_agent = get_pattern_agent()
    return {
        "status": "healthy",
        "agent": "pattern",
        "mongodb_uri_present": bool(os.getenv("MONGODB_URI")),
        "pattern_agent_initialized": pattern_agent is not None
    }