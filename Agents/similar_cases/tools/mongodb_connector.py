"""
MongoDB connector tool for Similar Cases Agent.
Handles connection and vector search operations.
"""

import os
from typing import Any, List, Dict
from pymongo import MongoClient
from dotenv import load_dotenv
from Agents.similar_cases.logger import logger

# Force reload environment variables
load_dotenv(override=True)


class MongoDBConnector:
    """Singleton MongoDB connector for vector search operations."""
    
    _instance = None
    _client = None
    _collection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBConnector, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize MongoDB connection (lazy loading)."""
        if self._client is None:
            self._connect()
    
    def _connect(self):
        """Establish MongoDB connection."""
        try:
            mongodb_uri = os.getenv("MONGODB_URI")
            database_name = os.getenv("DATABASE_NAME", "Capa")
            collection_name = os.getenv("COLLECTION_NAME", "Complaints")
            
            if not mongodb_uri:
                raise ValueError("MONGODB_URI not found in environment variables")
            
            logger.info(f"Connecting to MongoDB: {database_name}.{collection_name}")
            
            self._client = MongoClient(mongodb_uri)
            db = self._client[database_name]
            self._collection = db[collection_name]
            
            # Test connection
            self._client.admin.command('ping')
            logger.info("MongoDB connection established successfully")
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {str(e)}")
            raise
    
    def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 5000,
        threshold: float = 0.70,
        projection_fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector search on MongoDB Atlas - GENERIC & REUSABLE.
        
        Works with ANY collection that has embeddings.
        The embedding field name is configurable via EMBEDDING_FIELD env var.
        
        Args:
            query_embedding: Query vector embedding
            limit: Maximum number of results to return
            threshold: Minimum similarity threshold
            projection_fields: Fields to include in results
            
        Returns:
            List of matching documents with similarity scores
        """
        try:
            vector_index_name = os.getenv("VECTOR_INDEX_NAME", "vector_index")
            embedding_field = os.getenv("EMBEDDING_FIELD", "descriptionEmbedding")
            
            # Build projection
            projection = {"_id": 0}
            if projection_fields:
                for field in projection_fields:
                    projection[field] = 1
            projection["similarity"] = {"$meta": "vectorSearchScore"}
            
            # Build aggregation pipeline - GENERIC (works with any embedding field)
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": vector_index_name,
                        "path": embedding_field,  # Configurable embedding field
                        "queryVector": query_embedding,
                        "numCandidates": limit * 2,
                        "limit": limit,
                    }
                },
                {"$project": projection},
            ]
            
            logger.info(f"Running vector search on field '{embedding_field}' (limit={limit}, threshold={threshold})")
            
            # Execute search
            raw_results = list(self._collection.aggregate(pipeline))
            logger.info(f"Vector search returned {len(raw_results)} raw results")
            
            # Filter by threshold
            filtered_results = [
                doc for doc in raw_results 
                if doc.get("similarity", 0) >= threshold
            ]
            logger.info(f"Filtered to {len(filtered_results)} results above threshold")
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            raise
    
    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")


def get_mongodb_connector() -> MongoDBConnector:
    """Get MongoDB connector instance (singleton)."""
    return MongoDBConnector()
