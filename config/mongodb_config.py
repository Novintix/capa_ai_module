import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def get_mongodb_client():
    """
    Returns a MongoDB client and validates connection.
    """
    uri = os.getenv("MONGODB_URI", "")
    if not uri:
        raise ValueError("MONGODB_URI not found in environment variables.")
    
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        return client
    except Exception as e:
        raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}")

def get_complaints_collection():
    """
    Returns the legacy complaints collection.
    Kept for backwards compatibility — prefer get_capa_complaints_collection().
    """
    client = get_mongodb_client()
    db = client["capa-db"]
    collection = db["complaints"]
    return collection


def get_capa_complaints_collection():
    """
    Returns the centralised capa_complaints collection.
    Used by pattern agent and similar cases agent for vector search.
    """
    client = get_mongodb_client()
    db = client["capa-db"]
    return db["capa_complaints"]
