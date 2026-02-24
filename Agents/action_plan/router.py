"""
router.py

FastAPI route for CAPA Action Plan Agent.
"""

from fastapi import APIRouter, HTTPException
from .graph import build_graph
from .model import CapaActionPlanRequest, CapaActionPlanResponse

router = APIRouter()
graph = build_graph()


@router.post("/action_plan", response_model=CapaActionPlanResponse)
def generate_capa_action_plan(request: CapaActionPlanRequest):
    """
    Generate CAPA Action Plan from investigation and root cause data.
    
    Input:
    - investigation_summary
    - containment_actions
    - five_why_analysis
    - primary_root_cause
    - contributing_root_causes
    - systemic_root_causes
    - evidence_collected
    - root_cause_verification_status
    - severity_level
    - timeline_constraint
    - available_resources
    
    Output:
    - action_items (9-column action plan, audit-ready)
    - total_actions
    - primary_actions
    - preventive_systemic_actions
    - confidence_score
    - notes
    """
    try:
        # Invoke graph
        result = graph.invoke({
            "capa_input": request.capa_input.dict()
        })

        # Return response
        return CapaActionPlanResponse(
            action_items=result.get("action_items", []),
            total_actions=result.get("total_actions", 0),
            primary_actions=result.get("primary_actions", 0),
            preventive_systemic_actions=result.get("preventive_systemic_actions", 0),
            confidence_score=result.get("confidence_score", 0.0),
            notes=result.get("notes")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
