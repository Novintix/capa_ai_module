"""
router.py

Defines FastAPI routes for the Severity Agent.

Responsibilities:
- Accept incoming API requests
- Validate input using Pydantic models
- Trigger LangGraph execution
- Return structured severity response
- Log API request and response lifecycle
"""


from fastapi import APIRouter, HTTPException
from graph import build_graph
from model import SeverityRequest, SeverityResponse
router = APIRouter()

graph = build_graph()



# ----------------------------------------
# POST /severity
# ----------------------------------------
# Accepts a complaint issue description
# Invokes the severity graph
# Returns computed severity scores + label
# ----------------------------------------

# -------- API Route --------
@router.post("/severity", response_model=SeverityResponse)
def evaluate_severity(request: SeverityRequest):
    try:
        result = graph.invoke({
            "issue": request.issue
        })

        return SeverityResponse(
            clinical_score=result["clinical_score"],
            reversibility_score=result["reversibility_score"],
            medical_score=result["medical_score"],
            duration_score=result["duration_score"],
            severity_score=result["severity_score"],
            severity_label=result["severity_label"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
