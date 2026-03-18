from pydantic import BaseModel, Field
from typing import Optional


class SeverityLLMReasoning(BaseModel):
    clinical:      str = ""
    reversibility: str = ""
    medical:       str = ""
    duration:      str = ""


class SeverityLLMOutput(BaseModel):
    clinical_score:      int = Field(ge=1, le=10)
    reversibility_score: int = Field(ge=1, le=10)
    medical_score:       int = Field(ge=1, le=10)
    duration_score:      int = Field(ge=1, le=10)
    reasoning:           Optional[SeverityLLMReasoning] = None


# -------- Request Model --------
class SeverityRequest(BaseModel):
    issue: str


# -------- Response Model --------
class SeverityResponse(BaseModel):
    clinical_score:      int
    reversibility_score: int
    medical_score:       int
    duration_score:      int
    severity_score:      int
    severity_label:      str
    reasoning:           Optional[SeverityLLMReasoning] = None