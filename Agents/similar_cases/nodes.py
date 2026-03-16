"""
Node functions for Similar Cases Agent.
Each node performs a specific step in the workflow.
"""

from typing import Dict, Any
from datetime import datetime
from Agents.similar_cases.state import SimilarCasesState, SimilarCasesOutput, MatchResult
from Agents.similar_cases.tools.embedding_model import get_embedding_model
from Agents.similar_cases.tools.mongodb_connector import get_mongodb_connector
from Agents.similar_cases.logger import (
    log_node_start, log_node_end, log_embedding, 
    log_vector_search, log_error
)
import os
from dotenv import load_dotenv

# Force reload environment variables
load_dotenv(override=True)


def embed_query(state: SimilarCasesState) -> Dict[str, Any]:
    """
    Node 1: Convert user query to embedding vector.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with query_embedding
    """
    log_node_start("embed_query")
    
    try:
        query = state.input.query
        
        # Get embedding model and encode query
        embedding_model = get_embedding_model()
        query_embedding = embedding_model.encode(query, normalize=True)
        
        log_embedding(query, len(query_embedding))
        log_node_end("embed_query", f"Embedded query (dim={len(query_embedding)})")
        
        return {"query_embedding": query_embedding}
        
    except Exception as e:
        error_msg = f"Failed to embed query: {str(e)}"
        log_error("embed_query", error_msg)
        return {"error": error_msg}


def vector_search(state: SimilarCasesState) -> Dict[str, Any]:
    """
    Node 2: Perform vector search in MongoDB.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with all_similar results
    """
    log_node_start("vector_search")
    
    try:
        query_embedding = state.query_embedding
        
        # Get configuration
        similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.70"))
        vector_search_limit = int(os.getenv("VECTOR_SEARCH_LIMIT", "5000"))
        
        # Define projection fields
        projection_fields = [
            "recordId", "complaintId", "dateReceived", "source", "regionCountry",
            "severity", "productFamily", "site", "descriptionOfIssue", "status",
            "daysOpen", "assignedTo", "isNc", "ncId", "fieldAction", "euReportable",
            "fdaReportable", "capaNeeded", "capaId", "capaRationale", "repeated",
            "workflowStage"
        ]
        
        # Perform vector search
        mongodb_connector = get_mongodb_connector()
        results = mongodb_connector.vector_search(
            query_embedding=query_embedding,
            limit=vector_search_limit,
            threshold=similarity_threshold,
            projection_fields=projection_fields
        )
        
        log_vector_search(vector_search_limit, similarity_threshold, len(results))
        log_node_end("vector_search", f"Found {len(results)} similar cases")
        
        return {"all_similar": results}
        
    except Exception as e:
        error_msg = f"Vector search failed: {str(e)}"
        log_error("vector_search", error_msg)
        return {"error": error_msg}


def format_results(state: SimilarCasesState) -> Dict[str, Any]:
    """
    Node 3: Format final output with all results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with final_output
    """
    log_node_start("format_results")
    
    try:
        query = state.input.query
        all_similar = state.all_similar or []
        similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.70"))
        
        # Sort by similarity descending
        all_similar_sorted = sorted(
            all_similar, 
            key=lambda x: x.get("similarity", 0), 
            reverse=True
        )
        
        # Convert datetime objects and round similarity
        for match in all_similar_sorted:
            if "dateReceived" in match and hasattr(match["dateReceived"], "isoformat"):
                match["dateReceived"] = match["dateReceived"].isoformat()
            if "similarity" in match:
                match["similarity"] = round(match["similarity"], 4)
        
        similar_count = len(all_similar_sorted)
        
        # Build message
        if similar_count == 0:
            message = (
                f"No similar cases found above the {similarity_threshold:.0%} "
                f"similarity threshold for the given complaint description."
            )
        else:
            message = (
                f"Found {similar_count} similar case(s) above the "
                f"{similarity_threshold:.0%} similarity threshold."
            )
        
        # Create output
        output = SimilarCasesOutput(
            query=query,
            similarityThreshold=similarity_threshold,
            similarCount=similar_count,
            message=message,
            topMatches=[MatchResult(**match) for match in all_similar_sorted]
        )
        
        log_node_end("format_results", f"Formatted {similar_count} results")
        
        return {"final_output": output}
        
    except Exception as e:
        error_msg = f"Failed to format results: {str(e)}"
        log_error("format_results", error_msg)
        return {"error": error_msg}
