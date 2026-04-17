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
from Agents.pattern.router import router as pattern_router

from Agents.action_plan.router import router as action_plan_router
from Agents.zero_evidence_agent.router import router as zero_evidence_router


from Agents.action_plan.router import router as action_plan_router
from Agents.similar_cases.router import router as similar_cases_router
from Agents.ranking.router import router as ranking_router
from Agents.effectiveness.router import router as effectiveness_router
from Agents.validation.router import router as validation_router
from Agents.loop_control.router import router as loop_control_router

# # ── Orchestrator ──────────────────────────────────────────────────────────────
from orchestrator.risk_analysis_orchestrator_service.router import router as orchestrator_router
from orchestrator.why_analysis_orchestrator.router import router as why_analysis_router
from orchestrator.why_analysis_v2.router import router as why_analysis_v2_router
from orchestrator.why_analysis_v3.router import router as why_analysis_v3_router  # NEW: Simplified with human-in-the-loop
from orchestrator.rca_v2.router import router as rca_v2_router #updated why analysis orchestrator
from orchestrator.fishbone_v2.router import router as fishbone_v2_router  # NEW: Single-depth fishbone with 6M categorization
from orchestrator.fishbone_v3.router import router as fishbone_v3_router  # NEW: HITL Fishbone
from orchestrator.Root_cause_analysis.router import router as root_cause_analysis_router
from orchestrator.Root_cause_analysis_v2.router_v2 import router as root_cause_analysis_v2_router
from orchestrator.capa_director.router import router as director_router
from orchestrator.dynamic_builder.router import router as dynamic_builder_router


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
    app.include_router(action_plan_router)
    app.include_router(why_question_router)
    app.include_router(zero_evidence_router)
    app.include_router(why_analysis_router)
    app.include_router(why_analysis_v2_router)
    app.include_router(why_analysis_v3_router)  # NEW: Why Analysis V3
    app.include_router(rca_v2_router)
    app.include_router(fishbone_v2_router)  # NEW: Fishbone v2
    app.include_router(fishbone_v3_router)  # NEW: Fishbone v3 (HITL)
    app.include_router(root_cause_analysis_router)
    app.include_router(root_cause_analysis_v2_router)
    app.include_router(similar_cases_router)
    app.include_router(ranking_router)
    app.include_router(pattern_router)
    app.include_router(effectiveness_router)
    app.include_router(validation_router)
    app.include_router(loop_control_router)
    app.include_router(director_router)

    # # ── Orchestrator router ───────────────────────────────────────────────────
    app.include_router(orchestrator_router)  # exposes POST /capa/analyze
    app.include_router(dynamic_builder_router, prefix="/dynamic")
    
    @app.get("/")
    def root():
        """Health check endpoint"""
        return {
            "status": "online",
            "service": "Centralized Agent Repository",
            "version": "1.0.0",
            "message": "Use /fishbone_v3_test.html to access the UI",
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
                "zero_evidence": "Zero Evidence Mode Agent (First-Principles Cause Selection)",
                "why_analysis": "Why Analysis Orchestrator (Question → Cause Gen → Zero Evidence Pipeline)",
                "why_analysis_v2": "Why Analysis V2 Orchestrator (Question → Cause Gen → Validation → Loop Control)",
                "why_analysis_v3": "Why Analysis V3 Orchestrator (Question → Cause Gen → Validation → Human Review)",
                "rca_v2": "RCA v2 Orchestrator (State Machine Implementation with Controlled Memory)",
                "fishbone_v2": "Fishbone v2 Orchestrator (Single-Depth Analysis with 6M Categorization)",
                "fishbone_v3": "Fishbone v3 Orchestrator (Human-in-the-Loop Analysis with Decisions)",
                "root_cause_analysis": "Root Cause Analysis Coordinator (Top-level flow for Fishbone/Why and user checkpoints)",
                "similar_cases": "Similar Cases Search Agent (Vector Search)",
                "ranking": "Root Cause Ranking Agent (RCPS Methodology)",
                "pattern": "Pattern Analysis and Trend Recognition Agent",
                "effectiveness": "Effectiveness Evaluation Agent",
                "validation": "Generated Cause Validation Agent",
                "loop_control": "Loop Control Agent (RCA Continue/Stop Decision)",
                "orchestrator": "CAPA Analysis and Recommendation Orchestrator",
                "director": "CAPA Director (Overall Orchestrator) — Risk → RCA → Action Plan → Effectiveness"
                
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
                # "GET /health": "Global health check",
                "POST /severity": "Evaluate severity of a complaint issue",
                "POST /action_plan": "Generate FDA-compliant CAPA action plan",
                "POST /zero-evidence/": "Select Most Critical Functional Cause (Zero Evidence Mode)",
                "GET /zero-evidence/health": "Zero Evidence Agent health check",
                "POST /why-analysis/": "Run full Why Analysis pipeline (Question → Cause Gen → Zero Evidence)",
                "GET /why-analysis/health": "Why Analysis Orchestrator health check",
                "POST /why-analysis-v2/": "Run Why Analysis V2 (Question → Cause Gen → Validation → Loop Control with conditional ranking)",
                "GET /why-analysis-v2/health": "Why Analysis V2 Orchestrator health check",
                "POST /why-analysis-v3/": "Run Why Analysis V3 (Question → Cause Gen → Validation → Human Review)",
                "POST /why-analysis-v3/human-review": "Submit human cause selection for Why Analysis V3",
                "GET /why-analysis-v3/health": "Why Analysis V3 Orchestrator health check",
                "POST /rca-v2/": "Run RCA v2 Analysis with proper state machine (JSON input)",
                "POST /rca-v2/upload": "Run RCA v2 Analysis with file upload support",
                "GET /rca-v2/health": "RCA v2 Orchestrator health check",
                "POST /fishbone-v3/analyze": "Phase 1: Run Fishbone analysis and pause for human review",
                "POST /fishbone-v3/decide": "Phase 2: Submit human decisions (RCA, PROCEED) for causes",
                "POST /root-cause-analysis/start/why": "RCA checkpoint 1: start Why Analysis path",
                "POST /root-cause-analysis/start/fishbone": "RCA checkpoint 1: start Fishbone path",
                "POST /root-cause-analysis/select-category": "RCA checkpoint 3: choose Fishbone category and proceed to Why Analysis",
                "POST /root-cause-analysis/proceed-action-plan": "RCA checkpoint 2: confirm proceed to Action Plan and finish RCA flow",
                "GET /root-cause-analysis/status/{complaint_id}": "Get RCA coordinator session status",
                "POST /similar-cases/": "Find similar complaint cases using vector search",
                "GET /similar-cases/health": "Similar cases agent health check",
                "POST /ranking/": "Rank candidate root causes using RCPS methodology",
                "GET /ranking/health": "Ranking agent health check",
                "POST /pattern/": "Analyze trends and patterns in historical complaint data",
                "POST /effectiveness": "Evaluate effectiveness of CAPA actions",
                "POST /validation/": "Validate generated causes against complaint and investigation evidence",
                "GET /validation/health": "Validation agent health check",
                "POST /loop-control/analyze": "Decide LOOP, STOP_ROOT_FOUND, or STOP_DEGRADED for 5-Why RCA",
                "POST /capa/analyze": "Orchestrator endpoint to analyze a complaint and generate CAPA recommendations",
                "POST /director/analyze": "Top-level Director Orchestrator for full CAPA lifecycle (Risk, RCA, Action, Effectiveness)"
            }
        }
    
    @app.get("/health")
    def health_check():
        """Global health check"""
        return {
            "status": "healthy",
            "service": "Centralized Agent Repository"
        }


# Create FastAPI app instance
app = FastAPI(
    title="CAPA AI Module - Centralized Agent Repository",
    description="Centralized repository for all CAPA analysis agents and orchestrators",
    version="1.0.0"
)

# Register all routes
register_routes(app)
