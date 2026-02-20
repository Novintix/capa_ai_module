from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Cause(BaseModel):
    cause_id: str
    cause_text: str
    process_step: str
    failure_mode: str
    potential_effects: str
    severity: Optional[int] = None
    occurrence: Optional[int] = None
    detection: Optional[int] = None
    current_controls: Optional[str] = None
    source: str

class CategorizedCause(BaseModel):
    cause_id: str
    cause_text: str
    category: str = Field(..., description="Primary category: Man, Machine, Method, Material, Measurement, Environment, Unknown")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1 for primary category")
    secondary_categories: List[str] = Field(default_factory=list, description="Additional applicable categories if any")
    reasoning: str = Field(..., description="Explanation for the categorization")

class CategorizeInput(BaseModel):
    question: str
    causes: List[Cause]
    additional_context: Optional[str] = Field(None, description="Additional context for categorization")

class CategorizeOutput(BaseModel):
    categorized_causes: List[CategorizedCause]
    summary: Dict[str, int] = Field(default_factory=dict, description="Count per category")

class CategorizeState(BaseModel):
    input: CategorizeInput
    iteration: int = 0
    raw_categorizations: Optional[List[CategorizedCause]] = None
    final_output: Optional[CategorizeOutput] = None
