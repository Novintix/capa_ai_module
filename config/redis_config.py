import os
import redis
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# The URL from .env (e.g., redis://localhost:6379)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# A pre-configured Redis client object
# decode_responses=False is REQUIRED for LangGraph checkpointing
redis_client = redis.from_url(REDIS_URL, decode_responses=False)

# Re-use this everywhere to avoid multiple connection pools
def get_redis_client():
    return redis_client
