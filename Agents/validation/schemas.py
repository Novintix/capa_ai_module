"""
Validation Agent Schemas
Input/Output data models
"""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class GeneratedCause(BaseModel):
	"""Single generated cause to be validated."""

	cause_id: str = Field(..., description="Unique cause identifier")
	cause_text: str = Field(..., description="Cause description")
	process_step: Optional[str] = Field(None, description="Associated process step")
	failure_mode: Optional[str] = Field(None, description="Associated failure mode")
	potential_effects: Optional[str] = Field(None, description="Potential effects")
	severity: Optional[int] = Field(None, description="Severity rating from FMEA")
	occurrence: Optional[int] = Field(None, description="Occurrence rating from FMEA")
	detection: Optional[int] = Field(None, description="Detection rating from FMEA")
	current_controls: Optional[str] = Field(None, description="Current process controls")
	source: Optional[str] = Field(default="cause_generation", description="Source of the generated cause")


class ValidationInput(BaseModel):
	"""Input payload for validating generated causes against mapped evidence fields."""

	complaint_id: Optional[str] = Field(None, description="Complaint/CAPA identifier")
	question: Optional[str] = Field(None, description="Original why question from cause_generation output")
	generated_causes: List[GeneratedCause] = Field(..., description="List of generated causes to validate")
	complaint_description: str = Field(..., description="Complaint problem statement")
	logs: Optional[Any] = Field(None, description="Operational logs or event logs")
	reports: Optional[Any] = Field(None, description="Investigation reports and test reports")
	process_data: Optional[Any] = Field(None, description="Manufacturing/process data records")
	historical_capa: Optional[Any] = Field(None, description="Historical CAPA references")
	policies: Optional[Any] = Field(None, description="Policies related to process/compliance")
	sop: Optional[Any] = Field(None, description="SOP/work instructions")
	investigation_records: Optional[Any] = Field(None, description="General investigation records")
	supporting_system_information: Optional[Any] = Field(None, description="Additional system context")

	# Backward-compatible catch-all input
	investigation_evidence: Optional[Any] = Field(
		default=None,
		description="Optional legacy evidence payload; will be merged into evidence corpus",
	)


class CauseValidationResult(BaseModel):
	"""Validation decision for a single cause."""

	cause_id: str = Field(..., description="Cause identifier")
	cause_text: str = Field(..., description="Cause description")
	process_step: Optional[str] = Field(None, description="Associated process step")
	failure_mode: Optional[str] = Field(None, description="Associated failure mode")
	potential_effects: Optional[str] = Field(None, description="Potential effects")
	severity: Optional[int] = Field(None, description="Severity rating from FMEA")
	occurrence: Optional[int] = Field(None, description="Occurrence rating from FMEA")
	detection: Optional[int] = Field(None, description="Detection rating from FMEA")
	current_controls: Optional[str] = Field(None, description="Current process controls")
	source: Optional[str] = Field(None, description="Source of the generated cause")
	evidence_match_status: Literal["matched", "partially_matched", "no_evidence"] = Field(
		..., description="How strongly evidence supports this cause"
	)
	supporting_evidence_references: List[str] = Field(
		default_factory=list,
		description="Evidence reference IDs that support this cause",
	)
	confidence: float = Field(..., ge=0.0, le=1.0, description="Validation confidence for this cause")
	rationale: str = Field(..., description="Human-readable validation rationale")


class ValidationResult(BaseModel):
	"""Output for validated causes."""

	complaint_id: Optional[str] = Field(None, description="Complaint/CAPA identifier")
	complaint_description: str = Field(..., description="Original complaint description")
	total_input_causes: int = Field(..., description="Total generated causes received")
	total_validated_causes: int = Field(..., description="Total causes with evidence support")
	validated_causes: List[CauseValidationResult] = Field(
		default_factory=list,
		description="Only evidence-supported causes (matched or partially_matched)",
	)
	cause_validation_results: List[CauseValidationResult] = Field(
		default_factory=list,
		description="Validation status for each input cause",
	)
	overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence across validated causes")
	notes: Optional[str] = Field(None, description="Additional notes")
