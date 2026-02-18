from fastapi import FastAPI
from Agents.detection.router import api_router as detection_router


def register_routes(app: FastAPI):
    """
    Register all agent routes to the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    
    # Include agent routers
    app.include_router(detection_router)
    
    @app.get("/")
    def root():
        """Health check endpoint"""
        return {
            "status": "online",
            "service": "Centralized Agent Repository",
            "version": "1.0.0",
            "agents": {
                "detection": "Policy-Driven Detection Score Agent"
            },
            "endpoints": {
                "POST /detection/": "Calculate detection score with optional policy document",
                "GET /detection/health": "Detection agent health check",
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
