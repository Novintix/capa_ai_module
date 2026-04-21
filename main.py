import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

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

# Register API routes FIRST (before static files)
register_routes(app)

# Mount static files LAST (so API routes take precedence)
# This serves UI files at root, but API routes are checked first
# app.mount("/", StaticFiles(directory="UI", html=True), name="ui")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        port=8000,
        reload=True
    )
