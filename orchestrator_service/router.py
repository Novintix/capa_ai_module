from fastapi import APIRouter, HTTPException, Request
from orchestrator_service.model import RiskRequest, RiskResponse
from orchestrator_service.state import RiskAssessmentState
from orchestrator_service.utils import set_thread_ttl
import uuid

router = APIRouter()


@router.post("/analyze", response_model=RiskResponse)
async def analyze_risk(request: Request, risk_request: RiskRequest):
    try:
        # Get graph from app state
        graph = request.app.state.graph
        
        # 1. Generate unique request scope with namespace: orchestrator:v1:{user_id}:{request_id}
        request_id = risk_request.thread_id or str(uuid.uuid4())
        user_id = risk_request.user_id or "default_user"
        thread_id = f"orchestrator:v1:{user_id}:{request_id}"
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # ── Initialize state ──────────────────────────────────────────────────
        initial_state: RiskAssessmentState = {
            "complaint_id":          risk_request.complaint_id,
            "complaint_description": risk_request.complaint_description,
            "source":                risk_request.source,
            "date":                  risk_request.date,
            "product":               risk_request.product,
            "additional_context":    risk_request.additional_context,
            "similar_cases":         [c.model_dump() for c in risk_request.similar_cases],
            "structured_metadata":   risk_request.structured_metadata,
            "policy_path":          risk_request.policy_path,
            "errors":                [],
            "retry_counts":          {"severity": 0, "occurrence": 0, "detection": 0},
            "agent_outputs":         {},
            "workflow_status":      None,
            "escalation_required":   False,
            "escalation_reason":     "",
        }

        result = await graph.ainvoke(initial_state, config=config)
        
        # 3. Set TTL for this thread (7 days)
        await set_thread_ttl(thread_id)

        # ── Map flat state fields → RiskResponse ─────────────────────────────
        return RiskResponse(
            severity_score=result.get("severity_score"),
            occurrence_score=result.get("occurrence_score"),
            detection_score=result.get("detection_score"),
            rpn_value=result.get("rpn_value"),
            workflow_status=result.get("workflow_status", "unknown"),
            escalation_required=result.get("escalation_required", False),
            escalation_reason=result.get("escalation_reason"),
            conflict_detected=result.get("conflict_detected", False),
            errors=result.get("errors"),
            agent_outputs=result.get("agent_outputs"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state/{thread_id:path}")
async def get_session_state(request: Request, thread_id: str):
    """Retrieve the current state for a given thread_id from Redis."""
    try:
        graph = request.app.state.graph
        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.aget_state(config)
        
        if not state or not state.values:
            raise HTTPException(status_code=404, detail="Session state not found")
            
        return {
            "thread_id": thread_id,
            "values": state.values,
            "next": state.next,
            "metadata": state.metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch state: {str(e)}")


@router.post("/resume/{thread_id}", response_model=RiskResponse)
async def resume_session(request: Request, thread_id: str, updates: dict = None):
    """Resumes an existing session from the last checkpoint."""
    try:
        graph = request.app.state.graph
        config = {"configurable": {"thread_id": thread_id}}
        
        # Optionally apply updates to the state before resuming
        if updates:
            await graph.aupdate_state(config, updates)
            
        # Resume execution (None means resume from current state)
        result = await graph.ainvoke(None, config=config)
        
        # Set TTL for this thread (7 days)
        await set_thread_ttl(thread_id)
        
        return RiskResponse(
            severity_score=result.get("severity_score"),
            occurrence_score=result.get("occurrence_score"),
            detection_score=result.get("detection_score"),
            rpn_value=result.get("rpn_value"),
            workflow_status=result.get("workflow_status", "unknown"),
            escalation_required=result.get("escalation_required", False),
            escalation_reason=result.get("escalation_reason"),
            conflict_detected=result.get("conflict_detected", False),
            errors=result.get("errors"),
            agent_outputs=result.get("agent_outputs"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume session: {str(e)}")
