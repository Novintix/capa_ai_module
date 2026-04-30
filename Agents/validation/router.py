"""
Validation Agent API Router
Handles all validation endpoints
"""

from fastapi import APIRouter, HTTPException

from .agent import ValidationAgent
from .logger import log_api_request, log_api_response
from .schemas import ValidationInput, ValidationResult
from agent_ops import agentops_session


router = APIRouter(prefix="/validation", tags=["validation"])

_validation_agent = None


def get_validation_agent():
	"""Get or initialize validation agent (lazy initialization)."""
	global _validation_agent
	if _validation_agent is None:
		_validation_agent = ValidationAgent()
	return _validation_agent


@router.post("/", response_model=ValidationResult)
@agentops_session(name="validation@router.post(_, response_model=ValidationResult)", tags=["agents", "validation"])
def validate_generated_causes(payload: ValidationInput):
	"""
	Validate generated causes against complaint and investigation evidence.
	"""
	try:
		validation_agent = get_validation_agent()

		log_api_request(
			endpoint="/validation",
			complaint_id=payload.complaint_id or "N/A",
			cause_count=len(payload.generated_causes),
		)

		result = validation_agent.validate_causes(payload)

		log_api_response(
			complaint_id=payload.complaint_id or "N/A",
			validated_causes=result.get("total_validated_causes", 0),
			confidence=result.get("overall_confidence", 0.0),
		)

		return ValidationResult(**result)

	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Error validating causes: {exc}")


@router.get("/health")
def validation_health():
	"""Validation agent health check."""
	validation_agent = get_validation_agent()
	return {
		"status": "healthy",
		"agent": "validation",
		"agent_initialized": validation_agent is not None,
	}