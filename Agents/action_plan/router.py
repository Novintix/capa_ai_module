"""
router.py

FastAPI route for CAPA Action Plan Agent.
"""

from fastapi import APIRouter, HTTPException
from .graph import build_graph
from .model import CapaInput, CapaActionPlanResponse
from agent_ops import agentops_operation

router = APIRouter()
graph = build_graph()


@router.post("/action_plan", response_model=CapaActionPlanResponse)
@agentops_operation(name="action_plan")
def generate_capa_action_plan(request: CapaInput):
    """
    Generate CAPA Action Plan from investigation and root cause data.
    Accepts flat CapaInput fields directly — no nested wrapper needed.
    """
    try:
        result = graph.invoke(request.model_dump())

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
