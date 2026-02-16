"""
FastAPI Router for Detection Score Agent
Run: uvicorn router:app --reload
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from detection.agent import DetectionAgentLangGraph
from detection.schemas import ComplaintData, DetectionScore
from detection.logger import log_api_request, log_api_response

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Policy-Driven Detection Score Agent API",
    description="Calculate FMEA Detection Scores based on policy documents and complaint data",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
agent = DetectionAgentLangGraph()


@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Policy-Driven Detection Score Agent",
        "version": "2.0.0",
        "endpoints": {
            "POST /detect": "Calculate detection score without policy (default rules)",
            "POST /detect-with-policy": "Calculate detection score with policy document",
            "GET /health": "Health check"
        }
    }


@app.post("/detect", response_model=DetectionScore)
def detect_score(complaint: ComplaintData):
    """
    Calculate detection score using default FMEA rules (no policy document).
    
    The LLM uses comprehensive default detection rules to intelligently
    understand and score the complaint.
    
    Args:
        complaint: Complaint data with source and description
        
    Returns:
        DetectionScore with score, confidence, explanation, and decision_source="default_rules"
    """
    
    try:
        # Log request
        log_api_request("/detect", complaint.complaint_id, has_policy=False)
        
        # Calculate score without policy (uses default rules)
        result = agent.process_complaint(complaint, policy_document_path=None)
        
        # Log response
        log_api_response(complaint.complaint_id, result["detection_score"], result["decision_source"])
        
        return DetectionScore(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating detection score: {str(e)}"
        )


@app.post("/detect-with-policy", response_model=DetectionScore)
def detect_score_with_policy(complaint: ComplaintData, policy_path: str):
    """
    Calculate detection score using policy document.
    
    Extracts rules from the policy document and uses LLM to intelligently
    map the complaint to the appropriate policy rule.
    
    Args:
        complaint: Complaint data with source and description
        policy_path: Path to policy document (PDF, Word, Excel, or Image)
        
    Returns:
        DetectionScore with score, confidence, explanation, and decision_source="policy"
    """
    
    try:
        # Log request
        log_api_request("/detect-with-policy", complaint.complaint_id, has_policy=True)
        
        # Check if file exists
        if not os.path.exists(policy_path):
            raise HTTPException(
                status_code=404,
                detail=f"Policy document not found: {policy_path}"
            )
        
        # Process complaint with policy
        result = agent.process_complaint(complaint, policy_document_path=policy_path)
        
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


@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "google_api_key_present": bool(os.getenv("GOOGLE_API_KEY")),
        "azure_vision_key_present": bool(os.getenv("AZURE_VISION_KEY")),
        "agent_initialized": agent is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
