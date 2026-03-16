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
def generate_causes(question: QuestionInput, fmea_path: str = None):
    """
    Generate list of all possible causes based on "why" question
    
    This endpoint can work in two modes:
    1. **With FMEA Document**: Extracts causes from FMEA and validates with LLM
    2. **Without FMEA Document**: Generates causes using LLM expert knowledge
    
    Features:
    - LLM validation to filter irrelevant causes
    - Fallback generation when FMEA not available
    - Semantic matching for better accuracy
    - Reusable across different environments
    
    Example questions:
    - "Why did the bike stop?"
    - "Why is tablet strength incorrect?"
    - "Why was the syringe marking incorrect?"
    
    Args:
        question: Question input with why question
        fmea_path: Optional path to FMEA Excel document (if not provided, uses LLM generation)
        
    Returns:
        CauseGenerationResult with list of validated possible causes
    """
    
    try:
        # Get agent (lazy initialization)
        cause_agent = get_cause_agent()
        
        # Log request
        log_api_request("/cause-generation", question.question_id, has_fmea=bool(fmea_path))
        
        # Process question (agent handles missing FMEA internally)
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
