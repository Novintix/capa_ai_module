"""
Embedding model tool for Similar Cases Agent.
Handles text-to-vector conversion using sentence-transformers.
"""

import os
from typing import List
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from Agents.similar_cases.logger import logger

# Load environment variables
load_dotenv()


class EmbeddingModel:
    """Singleton embedding model for text-to-vector conversion."""
    
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingModel, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize embedding model (lazy loading)."""
        if self._model is None:
            self._load_model()
    
    def _load_model(self):
        """Load sentence-transformers model."""
        try:
            model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            logger.info(f"Loading embedding model: {model_name}")
            
            self._model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}")
            raise
    
    def encode(self, text: str, normalize: bool = True) -> List[float]:
        """
        Convert text to embedding vector.
        
        Args:
            text: Input text to embed
            normalize: Whether to normalize the embedding
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            embedding = self._model.encode(text, normalize_embeddings=normalize)
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Embedding encoding failed: {str(e)}")
            raise
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self._model.get_sentence_embedding_dimension()


def get_embedding_model() -> EmbeddingModel:
    """Get embedding model instance (singleton)."""
    return EmbeddingModel()
