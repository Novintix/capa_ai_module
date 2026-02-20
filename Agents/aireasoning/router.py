from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Optional
import json
from Agents.aireasoning.state import AIReasoningInput, AIReasoningResponse
from Agents.aireasoning.graph import aireasoning_graph
from Agents.aireasoning.logger import log_request, log_final_output, log_error, reset_log, log_output, log_output_audit

router = APIRouter(prefix="/aireasoning", tags=["aireasoning"])


@router.post("/analyze", response_model=AIReasoningResponse)
async def analyze_aireasoning(
    complaint_id: str = Form(...),
    risk_score: int = Form(...),
    pattern: str = Form(...),
    severity_level: str = Form(...),
    nc_source: str = Form(...),
    regulatory_impact: str = Form(...),
    customer_impact: str = Form(...),
    additional_context: Optional[str] = Form(None),
    # Generic additional data as JSON string
    additional_data_json: Optional[str] = Form(None, description="JSON string containing any additional data fields")
):
    """
    Generate AI reasoning for risk assessment.

    Accepts:
    - Form Data: risk assessment details including risk score, pattern, severity, impacts.
    - additional_data_json: Optional JSON string with any additional data fields (flexible schema)

    Example additional_data_json:
    {
        "occurrence_score": 8,
        "detection_score": 6,
        "severity_score": 9,
        "historical_data": "5 similar incidents",
        "root_cause": "Tooling wear",
        "capa_status": "Previous CAPA 60% effective",
        "process_capability": "Cpk = 1.15",
        "affected_lots": ["LOT-123", "LOT-145"],
        "customer_complaints": 12,
        "any_other_field": "any value"
    }

    Returns:
    - AI-generated reasoning with key factors, recommendations, and confidence level.
    """
    try:
        reset_log()  # Clear log for this new request
        log_request(complaint_id=complaint_id, risk_score=risk_score)

        # Validate risk score range
        if not (1 <= risk_score <= 100):
            raise HTTPException(status_code=400, detail="risk_score must be between 1 and 100")

        # Parse additional_data_json if provided
        additional_data = None
        if additional_data_json:
            try:
                additional_data = json.loads(additional_data_json)
                if not isinstance(additional_data, dict):
                    raise HTTPException(status_code=400, detail="additional_data_json must be a JSON object")
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON format for additional_data_json")

        # Build input state
        input_data = AIReasoningInput(
            complaint_id=complaint_id,
            risk_score=risk_score,
            pattern=pattern,
            severity_level=severity_level,
            nc_source=nc_source,
            regulatory_impact=regulatory_impact,
            customer_impact=customer_impact,
            additional_context=additional_context,
            additional_data=additional_data
        )

        # Validate required fields
        if not input_data.pattern.strip():
            raise HTTPException(status_code=400, detail="pattern cannot be empty")
        if not input_data.severity_level.strip():
            raise HTTPException(status_code=400, detail="severity_level cannot be empty")

        # Initialize state
        initial_state = {
            "input": input_data,
            "iteration": 0,
            "evidence_summary": None,
            "raw_reasoning": None,
            "final_output": None
        }

        # Invoke Graph
        result = aireasoning_graph.invoke(initial_state)
        final_output = result.get("final_output")

        if not final_output:
            raise ValueError("Agent failed to produce a final output")

        log_final_output(
            complaint_id=complaint_id,
            confidence=final_output.confidence_level
        )
        log_output(final_output.model_dump())
        log_output_audit(final_output.model_dump())

        return JSONResponse(content=final_output.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        log_error("router", str(e))
        raise HTTPException(status_code=500, detail=f"Error processing AI reasoning: {str(e)}")
