from fastapi import FastAPI
from Agents.detection.router import router as detection_router
from Agents.severity.router import router as severity_router
from Agents.regulatory.router import router as regulatory_router
from Agents.occurrence.router import router as occurrence_router
from Agents.aireasoning.router import router as aireasoning_router
from Agents.categorize.router import router as categorize_router
from Agents.cause_generation.router import router as cause_generation_router
from Agents.question.router import router as why_question_router
from Agents.action_plan.router import router as action_plan_router
from orchestrator_service.router import router as orchestrator_router


def register_routes(app: FastAPI):
    """
    Register all agent and orchestrator routes to the FastAPI app.
    
    Organizes routes by functional category:
    - Orchestrator: Master workflow orchestration
    - Risk Assessment Agents: Detection, Severity, Occurrence
    - Analysis Agents: Categorization, Cause Generation, Regulatory
    - Support Agents: AI Reasoning, 5 Whys, Action Plan
    
    Args:
        app: FastAPI application instance
    """
    
    # ─────────────────────────────────────────────────────────────
    # Master Orchestrator Service
    # ─────────────────────────────────────────────────────────────
    app.include_router(orchestrator_router, prefix="/orchestration", tags=["Orchestration"])
    
    # ─────────────────────────────────────────────────────────────
    # Risk Assessment Agents
    # ─────────────────────────────────────────────────────────────
    app.include_router(detection_router, tags=["Risk Assessment"])
    app.include_router(severity_router, tags=["Risk Assessment"])
    app.include_router(occurrence_router, tags=["Risk Assessment"])
    
    # ─────────────────────────────────────────────────────────────
    # Analysis & Root Cause Agents
    # ─────────────────────────────────────────────────────────────
    app.include_router(aireasoning_router, tags=["Analysis"])
    app.include_router(categorize_router, tags=["Analysis"])
    app.include_router(cause_generation_router, tags=["Root Cause Analysis"])
    app.include_router(regulatory_router, tags=["Compliance"])
    
    # ─────────────────────────────────────────────────────────────
    # Support & Question Agents
    # ─────────────────────────────────────────────────────────────
    app.include_router(why_question_router, tags=["Support"])
    app.include_router(action_plan_router, tags=["Support"])
    
    @app.get("/", tags=["System"])
    def root():
        """API root endpoint with service overview"""
        return {
            "status": "online",
            "service": "Centralized CAPA Risk Assessment Platform",
            "version": "2.0.0",
            "architecture": {
                "type": "Distributed Multi-Agent System with Master Orchestrator",
                "orchestration": "LangGraph with Redis state persistence"
            },
            "components": {
                "orchestrator": "Master workflow orchestrator - coordinates all agents",
                "risk_assessment": ["Detection Score", "Severity Rating", "Occurrence Rating"],
                "analysis": ["AI Reasoning", "6M Categorization (Fishbone)", "Cause Generation"],
                "compliance": ["Regulatory Compliance Evaluation", "CAPA Action Planning"],
                "support": ["5 Whys Question Chain", "FDA-compliant Documentation"]
            },
            "agents": {
                "detection": "Policy-Driven Detection Score Agent",
                "severity": "Severity Classification Agent",
                "occurrence": "Occurrence Rating Agent",
                "aireasoning": "AI Reasoning Agent",
                "categorize": "6M Categorization Agent (Fishbone)",
                "cause_generation": "FMEA-Based Cause Generation Agent",
                "regulatory": "Regulatory Compliance Agent",
                "why_question": "Why Question Agent (5 Whys)",
                "action_plan": "CAPA Action Plan Generator",
            },
            "endpoints": {
                "orchestration": {
                    "POST /orchestration/analyze": "Master workflow - analyzes complaint end-to-end",
                    "GET /orchestration/state/{thread_id}": "Get workflow state snapshot",
                    "POST /orchestration/resume/{thread_id}": "Resume paused workflow"
                },
                "risk_assessment": {
                    "POST /detection/": "Calculate detection score with optional policy document",
                    "GET /detection/health": "Detection agent health check",
                    "POST /severity": "Evaluate severity of complaint issue",
                    "POST /occurrence/analyze": "Analyze occurrence rating for complaint",
                    "POST /categorize/analyze": "Categorize causes into 6M categories"
                },
                "analysis": {
                    "POST /aireasoning/analyze": "Generate AI reasoning for risk assessment",
                    "POST /cause-generation/": "Generate causes from FMEA document",
                    "GET /cause-generation/health": "Cause generation agent health check",
                },
                "compliance": {
                    "POST /regulatory/": "Evaluate regulatory compliance and reporting requirements",
                    "GET /regulatory/health": "Regulatory agent health check",
                    "POST /action_plan": "Generate FDA-compliant CAPA action plan",
                },
                "support": {
                    "POST /why/start": "Start new 5 Whys chain (stores context in Redis)",
                    "POST /why/continue": "Continue Why chain (complaint_id + answer only)",
                    "GET /why/health": "Why Question agent health check",
                },
                "system": {
                    "GET /": "This endpoint - service overview",
                    "GET /health": "Global health check"
                }
            }
        }
    
    @app.get("/health", tags=["System"])
    def health_check():
        """Global system health check"""
        return {
            "status": "healthy",
            "service": "Centralized CAPA Risk Assessment Platform",
            "version": "2.0.0",
            "timestamp": None  # Can be populated with current timestamp
        }
