"""
Ranking Agent API Router
Handles root cause ranking endpoints
"""

from fastapi import APIRouter, HTTPException
from Agents.ranking.state import RankingInput, RankingOutput, RankingConfig
from Agents.ranking.logger import log_api_request, log_api_response
from Agents.ranking.agent import RankingAgent
from agent_ops import agentops_session


# Create API router
router = APIRouter(prefix="/ranking", tags=["ranking"])

# Lazy initialization of agent
_ranking_agent = None


def get_ranking_agent():
    """Get or initialize the ranking agent (lazy initialization)"""
    global _ranking_agent
    if _ranking_agent is None:
        _ranking_agent = RankingAgent()
    return _ranking_agent


@router.post("/", response_model=RankingOutput)
@agentops_session(name="ranking@router.post(_, response_model=RankingOutput)", tags=["agents", "ranking"])
def rank_causes(request: RankingInput):
    """
    Rank candidate root causes using configurable RCPS methodology.
    
    REUSABLE FOR ANY DOMAIN - Manufacturing, Software, Healthcare, etc.
    
    The Root Cause Priority Score (RCPS) is calculated using configurable weights:
    - Default: 35% Risk Priority Number (RPN) + 30% Evidence + 20% Mechanism + 15% Proximity
    - Customizable per domain and use case
    
    Input Format (Generic):
    - cause_id: Unique identifier
    - cause_text: Description of potential cause
    - context_step: Context/process where issue occurs
    - issue_type: Type of issue/failure
    - impact_description: Effects/impact of the issue
    - severity, occurrence, detection: 1-10 scores
    - metadata: Optional domain-specific data
    
    Configuration Options:
    - domain: Context name (e.g., 'manufacturing', 'software')
    - weights: Custom RCPS calculation weights
    - max_causes: Maximum causes to process
    - evaluation contexts: Custom prompts for evidence/mechanism/proximity
    
    Examples:
    - Manufacturing FMEA: process_step → context_step, failure_mode → issue_type
    - Software Bugs: component → context_step, bug_type → issue_type
    - Healthcare Issues: procedure → context_step, symptom → issue_type
    
    Returns causes ranked by RCPS with LLM-based justifications.
    
    Args:
        request: RankingInput with causes and optional configuration
        
    Returns:
        RankingOutput with ranked causes and configuration used
        
    Raises:
        HTTPException: 400 for validation errors, 500 for processing errors
    """
    try:
        # Get configuration (use defaults if not provided)
        config = request.config or RankingConfig()
        
        # Additional business logic validation
        if len(request.causes) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 causes are required for meaningful ranking comparison"
            )
        
        if len(request.causes) > config.max_causes:
            raise HTTPException(
                status_code=400,
                detail=f"Too many causes: {len(request.causes)}. Maximum allowed for {config.domain}: {config.max_causes}"
            )
        
        # Validate RPN calculations don't overflow
        for cause in request.causes:
            rpn = cause.severity * cause.occurrence * cause.detection
            if rpn > 1000:  # Reasonable upper limit
                raise HTTPException(
                    status_code=400,
                    detail=f"RPN too high for cause {cause.cause_id}: {rpn}. Check severity/occurrence/detection scores."
                )
        
        # Get agent (lazy initialization)
        agent = get_ranking_agent()
        
        # Log request with domain context
        log_api_request(f"/ranking ({config.domain})", len(request.causes))
        
        # Rank causes with configuration
        result = agent.rank_causes([c.dict() for c in request.causes], config.dict())
        
        # Log response
        log_api_response(result.total_causes, result.selected_root_cause)
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during ranking: {str(e)}"
        )


@router.get("/health")
def ranking_health():
    """Ranking agent health check"""
    agent = get_ranking_agent()
    
    return {
        "status": "healthy",
        "agent": "ranking",
        "methodology": "RCPS (Root Cause Priority Score)",
        "weights": {
            "rpn": 0.35,
            "evidence": 0.30,
            "mechanism": 0.20,
            "proximity": 0.15
        },
        "agent_initialized": agent is not None
    }