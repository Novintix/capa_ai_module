"""
router.py

FastAPI route for CAPA Effectiveness Evaluation Agent.
"""

from fastapi import APIRouter, HTTPException
from .graph import build_graph
from .model import EffectivenessEvaluationRequest, EffectivenessEvaluationResponse

router = APIRouter()
graph = build_graph()

@router.post("/effectiveness", response_model=EffectivenessEvaluationResponse)
def evaluate_effectiveness(request: EffectivenessEvaluationRequest):
    """
    Evaluate CAPA Action Plan effectiveness.
    """
    try:
        # Invoke graph
        result = graph.invoke({
            "evaluation_input": request.evaluation_input.dict()
        })

        # Return response
        return EffectivenessEvaluationResponse(
            evaluated_actions=result.get("evaluated_actions", []),
            confidence_score=result.get("confidence_score", 0.0),
            notes=result.get("notes")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
