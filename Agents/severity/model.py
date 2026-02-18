from pydantic import BaseModel, Field


class SeverityLLMOutput(BaseModel):
    clinical_score: int = Field(ge=1, le=10)
    reversibility_score: int = Field(ge=1, le=10)
    medical_score: int = Field(ge=1, le=10)
    duration_score: int = Field(ge=1, le=10)

# -------- Request Model --------
class SeverityRequest(BaseModel):
    issue: str


# -------- Response Model --------
class SeverityResponse(BaseModel):
    clinical_score: int
    reversibility_score: int
    medical_score: int
    duration_score: int
    severity_score: int
    severity_label: str