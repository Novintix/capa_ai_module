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
    Returns the complaints collection.
    """
    client = get_mongodb_client()
    db = client["capa-db"]
    collection = db["complaints"]
    return collection
