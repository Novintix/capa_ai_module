from fastapi import FastAPI
from Agents.detection.router import api_router as detection_router
from Agents.severity.router import router as severity_router
from Agents.regulatory.router import api_router as regulatory_router
from Agents.occurrence.router import router as occurrence_router
from Agents.aireasoning.router import router as aireasoning_router
from Agents.question.router import router as why_question_router


def register_routes(app: FastAPI):
    """
    Register all agent routes to the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    
    # Include agent routers
    app.include_router(detection_router)
    app.include_router(occurrence_router)
    app.include_router(aireasoning_router)
    app.include_router(why_question_router)
    
    @app.get("/")
    def root():
        """Health check endpoint"""
        return {
            "status": "online",
            "service": "Centralized Agent Repository",
            "version": "1.0.0",
            "agents": {
                "detection": "Policy-Driven Detection Score Agent",
                "occurrence": "Occurrence Rating Agent",
                "aireasoning": "AI Reasoning Agent",
                "why_question": "Why Question Agent (5 Whys)"
            },
            "endpoints": {
                "POST /detection/": "Calculate detection score with optional policy document",
                "GET /detection/health": "Detection agent health check",
                "POST /occurrence/analyze": "Analyze occurrence rating for a complaint",
                "POST /aireasoning/analyze": "Generate AI reasoning for risk assessment",
                "POST /why/start": "Start a new 5 Whys chain (stores context in Redis)",
                "POST /why/continue": "Continue an existing Why chain (complaint_id + answer only)",
                "GET /why/health": "Why Question agent health check",
                "GET /health": "Global health check"
            }
        }
    
    @app.get("/health")
    def health_check():
        """Global health check"""
        return {
            "status": "healthy",
            "service": "Centralized Agent Repository"
        }
