import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.redis import AsyncRedisSaver
from dotenv import load_dotenv

from router import register_routes
from orchestrator_service.graph import build_graph

# Load environment variables
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Initializes Redis checkpointer and builds LangGraph on startup.
    Graceful shutdown on app termination.
    """
    # Initialize Redis connection and async checkpointer
    async with AsyncRedisSaver.from_conn_string(REDIS_URL) as memory:
        # Build orchestrator graph with persistent state management
        app.state.graph = build_graph(checkpointer=memory)
        yield
        # Cleanup happens automatically when exiting context


# Initialize FastAPI app with enhanced metadata
app = FastAPI(
    title="CAPA Risk Assessment Platform",
    description="Centralized multi-agent system for CAPA risk assessment and compliance",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routes (individual agents + orchestrator)
register_routes(app)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
