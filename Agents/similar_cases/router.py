"""
Similar Cases Agent API Router
Handles all similarity search endpoints - REUSABLE for any data type
"""

from fastapi import APIRouter, HTTPException
from Agents.similar_cases.state import SimilarCasesInput, SimilarCasesOutput
from Agents.similar_cases.logger import log_api_request, log_api_response
from Agents.similar_cases.agent import SimilarCasesAgent


# Create API router
router = APIRouter(prefix="/similar-cases", tags=["similar-cases"])

# Lazy initialization of agent
_similar_cases_agent = None


def get_similar_cases_agent():
    """Get or initialize the similar cases agent (lazy initialization)"""
    global _similar_cases_agent
    if _similar_cases_agent is None:
        _similar_cases_agent = SimilarCasesAgent()
    return _similar_cases_agent


@router.post("/", response_model=SimilarCasesOutput)
def find_similar_cases(request: SimilarCasesInput):
    """
    Find similar items using vector search - GENERIC & REUSABLE.
    
    Works with ANY data type that has embeddings:
    - Complaints, diseases, patient profiles, products, documents, etc.
    
    Searches MongoDB Atlas for items semantically similar to the provided
    query using sentence-transformers embeddings and cosine similarity.
    
    Configuration (via .env):
    - MONGODB_URI: Your MongoDB connection string
    - DATABASE_NAME: Your database name
    - COLLECTION_NAME: Your collection name (complaints, diseases, profiles, etc.)
    - EMBEDDING_FIELD: Field containing embeddings (default: descriptionEmbedding)
    - SIMILARITY_THRESHOLD: Minimum similarity (default: 0.70)
    
    Args:
        request: SimilarCasesInput with query text
        
    Returns:
        SimilarCasesOutput with matching items above similarity threshold
    """
    try:
        # Get agent (lazy initialization)
        agent = get_similar_cases_agent()
        
        # Log request
        log_api_request("/similar-cases", request.query)
        
        # Find similar cases
        result = agent.find_similar_cases(request.query)
        
        # Log response
        log_api_response(result.similarCount)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error finding similar cases: {str(e)}"
        )


@router.get("/health")
def similar_cases_health():
    """Similar cases agent health check"""
    import os
    agent = get_similar_cases_agent()
    
    return {
        "status": "healthy",
        "agent": "similar_cases",
        "mongodb_uri_present": bool(os.getenv("MONGODB_URI")),
        "database": os.getenv("DATABASE_NAME", "Not Set"),
        "collection": os.getenv("COLLECTION_NAME", "Not Set"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        "embedding_field": os.getenv("EMBEDDING_FIELD", "descriptionEmbedding"),
        "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.70")),
        "agent_initialized": agent is not None
    }
