import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from Agents.detection.agent import DetectionAgentLangGraph
from router import register_routes

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Agents",
    description="Centralized repository for all agents",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents
detection_agent = DetectionAgentLangGraph()

# Register routes
register_routes(app, detection_agent)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
