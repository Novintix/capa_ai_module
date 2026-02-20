"""
Semantic Matching using Embeddings
Optional semantic similarity for better question-to-FMEA matching
"""

from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

# Lazy load sentence-transformers
_model = None


def get_embedding_model():
    """Lazy load sentence-transformers model"""
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """
    Calculate semantic similarity between two texts using embeddings
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score (0-1)
    """
    try:
        model = get_embedding_model()
        
        # Generate embeddings
        embeddings = model.encode([text1, text2])
        
        # Calculate cosine similarity
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        )
        
        return float(similarity)
        
    except Exception as e:
        # Fallback to 0 if embedding fails
        return 0.0


def rank_fmea_by_semantic_similarity(
    question: str,
    fmea_data: List[Dict[str, Any]],
    threshold: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Rank FMEA rows by semantic similarity to question
    
    Args:
        question: Why question
        fmea_data: List of FMEA rows
        threshold: Minimum similarity threshold (0-1)
        
    Returns:
        List of FMEA rows with similarity scores, sorted by relevance
    """
    try:
        model = get_embedding_model()
        
        # Generate question embedding
        question_embedding = model.encode([question])[0]
        
        # Calculate similarity for each FMEA row
        ranked_rows = []
        
        for row in fmea_data:
            # Combine searchable fields
            process_step = str(row.get("process_step", ""))
            failure_mode = str(row.get("failure_mode", ""))
            effects = str(row.get("effects", ""))
            causes = str(row.get("causes", ""))
            
            fmea_text = f"{process_step} {failure_mode} {effects} {causes}"
            
            # Generate FMEA embedding
            fmea_embedding = model.encode([fmea_text])[0]
            
            # Calculate cosine similarity
            similarity = np.dot(question_embedding, fmea_embedding) / (
                np.linalg.norm(question_embedding) * np.linalg.norm(fmea_embedding)
            )
            
            # Only include if above threshold
            if similarity >= threshold:
                row["semantic_similarity"] = float(similarity)
                ranked_rows.append(row)
        
        # Sort by similarity (highest first)
        ranked_rows.sort(key=lambda x: x.get("semantic_similarity", 0), reverse=True)
        
        return ranked_rows
        
    except Exception as e:
        # Fallback to returning all rows if embedding fails
        return fmea_data
