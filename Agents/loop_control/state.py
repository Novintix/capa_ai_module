"""
State and schema models for the Loop Control agent.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


DecisionType = Literal["STOP_ROOT_FOUND", "LOOP", "STOP_DEGRADED"]
TrendType = Literal["increasing", "stable", "decreasing"]
ScoreBand = Literal[1, 2, 3]


class WhyChainItem(BaseModel):
	loop: int = Field(..., ge=1)
	question: str = Field(..., min_length=1)
	cause: str = Field(..., min_length=1)
	confidence: float = Field(..., ge=0.0, le=1.0)


class LoopControlInput(BaseModel):
	incident_description: str = Field(..., min_length=1)
	current_loop_count: int = Field(..., ge=0)
	max_loops: int = Field(..., ge=1)
	current_top_cause: str = Field(..., min_length=1)
	current_cause_confidence: float = Field(..., ge=0.0, le=1.0)
	fmea_document_path: Optional[str] = None
	full_why_chain: list[WhyChainItem] = Field(default_factory=list)


class ChainHealth(BaseModel):
	circular: bool
	specificity_trend: TrendType
	confidence_trend: TrendType


class RootCauseScore(BaseModel):
	actionability: ScoreBand
	system_depth: ScoreBand
	recurrence_prevention: ScoreBand
	total: int = Field(..., ge=3, le=9)


class LoopSignals(BaseModel):
	fmea_gap: bool
	degraded: bool
	boundary_crossed: bool
	team_cannot_fix: bool
	alignment: Literal["strong", "weak", "none"]
	llm_fallback: bool = False
	llm_fallback_reason: Optional[str] = None


class NextStep(BaseModel):
	target: str
	probe_angle: str
	avoid: str
	evidence_hint: str


class LoopControlOutput(BaseModel):
	decision: DecisionType
	reasoning: str
	chain_health: ChainHealth
	root_cause_score: RootCauseScore
	next_step: Optional[NextStep]


class LoopControlState(BaseModel):
	input: LoopControlInput
	chain_health: Optional[ChainHealth] = None
	root_cause_score: Optional[RootCauseScore] = None
	loop_signals: Optional[LoopSignals] = None
	decision: Optional[DecisionType] = None
	reasoning: Optional[str] = None
	next_step: Optional[NextStep] = None
	final_output: Optional[LoopControlOutput] = None

