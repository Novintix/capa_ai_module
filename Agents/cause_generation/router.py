"""
Cause Generation Agent API Router
Handles all cause generation endpoints
"""

import os
from fastapi import APIRouter, HTTPException

from .schemas import QuestionInput, CauseGenerationResult
from .logger import log_api_request, log_api_response
from .agent import CauseGenerationAgent


# Create API router
router = APIRouter(prefix="/cause-generation", tags=["cause-generation"])

# Lazy initialization of agent
_cause_agent = None


def get_cause_agent():
    """Get or initialize the cause generation agent (lazy initialization)"""
    global _cause_agent
    if _cause_agent is None:
        _cause_agent = CauseGenerationAgent()
    return _cause_agent


@router.post("/", response_model=CauseGenerationResult)
def generate_causes(question: QuestionInput, fmea_path: str):
    """
    Generate list of all possible causes from FMEA document based on "why" question
    
    This endpoint:
    - Parses the FMEA document
    - Extracts keywords from the why question
    - Matches question to relevant FMEA entries
    - Returns ALL possible causes from matched entries
    
    Does NOT:
    - Rank or validate causes (handled by downstream agents)
    - Calculate occurrence/detection/RPN
    - Use historical data
    
    Example questions:
    - "Why did the bike stop?"
    - "Why is tablet strength incorrect?"
    - "Why is there content uniformity failure?"
    
    Args:
        question: Question input with why question
        fmea_path: Path to FMEA Excel document
        
    Returns:
        CauseGenerationResult with list of all possible causes
    """
    
    try:
        # Get agent (lazy initialization)
        cause_agent = get_cause_agent()
        
        # Log request
        log_api_request("/cause-generation", question.question_id, has_fmea=bool(fmea_path))
        
        # Check if FMEA file exists
        if not os.path.exists(fmea_path):
            raise HTTPException(
                status_code=404,
                detail=f"FMEA document not found: {fmea_path}"
            )
        
        # Process question
        result = cause_agent.process_question(question, fmea_path)
        
        # Log response
        log_api_response(question.question_id, result["total_causes"])
        
        return CauseGenerationResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating causes: {str(e)}"
        )


@router.get("/health")
def cause_generation_health():
    """Cause generation agent health check"""
    cause_agent = get_cause_agent()
    return {
        "status": "healthy",
        "agent": "cause_generation",
        "agent_initialized": cause_agent is not None
    }
