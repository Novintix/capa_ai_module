import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

async def set_thread_ttl(thread_id: str, ttl_seconds: int = 60 * 60 * 24 * 7):
    """
    Sets a TTL for all Redis keys associated with a specific LangGraph thread.
    Default is 7 days.
    """
    try:
        r = redis.from_url(REDIS_URL)
        # LangGraph Redis keys look like:
        # checkpoint:<thread_id>
        # checkpoint:<thread_id>:<checkpoint_id>
        # writes:<thread_id>:...
        
        # We search for keys matching the thread_id
        # Note: In production, scan_iter is safer than keys()
        async for key in r.scan_iter(f"*:{thread_id}*"):
            await r.expire(key, ttl_seconds)
            
        await r.aclose()
    except Exception as e:
        # Log error but don't fail the request
        print(f"Failed to set TTL for thread {thread_id}: {e}")
