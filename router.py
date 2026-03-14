from fastapi import FastAPI
from Agents.detection.router import router as detection_router
from Agents.severity.router import router as severity_router
from Agents.regulatory.router import router as regulatory_router
from Agents.occurrence.router import router as occurrence_router
from Agents.aireasoning.router import router as aireasoning_router
from Agents.categorize.router import router as categorize_router
from Agents.cause_generation.router import router as cause_generation_router
from Agents.question.router import router as why_question_router
from Agents.ingestion.router import router as ingestion_router
from Agents.action_plan.router import router as action_plan_router
from Agents.zero_evidence_agent.router import router as zero_evidence_router

def register_routes(app: FastAPI):
    """
    Register all agent routes to the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    
    # Include agent routers
    app.include_router(detection_router)
    app.include_router(regulatory_router)
    app.include_router(cause_generation_router)
    app.include_router(ingestion_router)
    app.include_router(occurrence_router)
    app.include_router(aireasoning_router)
    app.include_router(occurrence_router)
    app.include_router(aireasoning_router)
    app.include_router(categorize_router)
    app.include_router(severity_router)
    app.include_router(regulatory_router)
    app.include_router(action_plan_router)
    app.include_router(why_question_router)
    app.include_router(zero_evidence_router)
    
    @app.get("/")
    def root():
        """Health check endpoint"""
        return {
            "status": "online",
            "service": "Centralized Agent Repository",
            "version": "1.0.0",
            "agents": {
                "detection": "Policy-Driven Detection Score Agent",
                "regulatory": "Regulatory Compliance Agent",
                "cause_generation": "FMEA-Based Cause Generation Agent",
                "occurrence": "Occurrence Rating Agent",
                "aireasoning": "AI Reasoning Agent",
                "categorize": "6M Categorization Agent (Fishbone)",
                "severity": "Severity Classification Agent",
                "action_plan": "CAPA Action Plan Generator",
                "why_question": "Why Question Agent (5 Whys)",
                "zero_evidence": "Zero Evidence Mode Agent (First-Principles Cause Selection)"
            },
            "endpoints": {
                "POST /detection/": "Calculate detection score with optional policy document",
                "GET /detection/health": "Detection agent health check",
                "POST /regulatory/": "Evaluate regulatory compliance and reporting requirements",
                "GET /regulatory/health": "Regulatory agent health check",
                "POST /cause-generation/": "Generate causes from FMEA document",
                "GET /cause-generation/health": "Cause generation agent health check",
                "POST /occurrence/analyze": "Analyze occurrence rating for a complaint",
                "POST /aireasoning/analyze": "Generate AI reasoning for risk assessment",
                "POST /categorize/analyze": "Categorize causes into 6M categories (Fishbone)",
                "POST /why/start": "Start a new 5 Whys chain (stores context in Redis)",
                "POST /why/continue": "Continue an existing Why chain (complaint_id + answer only)",
                "GET /why/health": "Why Question agent health check",
                "GET /health": "Global health check",
                "POST /severity": "Evaluate severity of a complaint issue",
                "POST /action_plan": "Generate FDA-compliant CAPA action plan",
                "POST /zero-evidence/": "Select Most Critical Functional Cause (Zero Evidence Mode)",
                "GET /zero-evidence/health": "Zero Evidence Agent health check",
            }
        }
    
    @app.get("/health")
    def health_check():
        """Global health check"""
        return {
            "status": "healthy",
            "service": "Centralized Agent Repository"
        }
