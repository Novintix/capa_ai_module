from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class EvidenceType(str, Enum):
    """Evidence strength types with scores."""
    OBSERVABLE = "observable"      # 1.0 - Direct logs, measurements, inspection records
    INDIRECT = "indirect"          # 0.7 - Operator observations, visual checks
    HISTORICAL = "historical"      # 0.5 - Previous cases, maintenance records
    NONE = "none"                 # 0.3 - No supporting evidence


class MechanismFit(str, Enum):
    """Mechanism fit types with scores."""
    STRONG = "strong"             # 0.9 - Direct technical relationship
    MODERATE = "moderate"         # 0.7 - Partial technical relationship
    WEAK = "weak"                 # 0.4 - Weak technical relationship


class CausalProximity(str, Enum):
    """Causal proximity types with scores."""
    DIRECT = "direct"             # 1.0 - Immediate trigger
    CONTRIBUTOR = "contributor"   # 0.7 - Secondary factor
    BACKGROUND = "background"     # 0.4 - Distant cause


class RCPSWeights(BaseModel):
    """Configurable RCPS calculation weights."""
    rpn_weight: float = Field(default=0.35, ge=0.0, le=1.0, description="RPN weight (default: 35%)")
    evidence_weight: float = Field(default=0.30, ge=0.0, le=1.0, description="Evidence weight (default: 30%)")
    mechanism_weight: float = Field(default=0.20, ge=0.0, le=1.0, description="Mechanism weight (default: 20%)")
    proximity_weight: float = Field(default=0.15, ge=0.0, le=1.0, description="Proximity weight (default: 15%)")
    
    @field_validator('rpn_weight', 'evidence_weight', 'mechanism_weight', 'proximity_weight')
    @classmethod
    def validate_weights_sum_to_one(cls, v, info):
        """Validate that all weights sum to 1.0."""
        if hasattr(info, 'data') and len(info.data) == 4:
            total = sum(info.data.values())
            if abs(total - 1.0) > 0.001:
                raise ValueError("All weights must sum to 1.0")
        return v


class CauseInput(BaseModel):
    """Generic input schema for a single cause candidate - adaptable to any domain."""
    cause_id: str = Field(..., min_length=1, max_length=50, pattern=r'^[A-Za-z0-9_-]+$', description="Unique identifier")
    cause_text: str = Field(..., min_length=10, max_length=1000, description="Description of the potential cause")
    
    # Flexible field names - supports both generic and FMEA-specific naming
    context_step: Optional[str] = Field(None, min_length=3, max_length=200, description="Context/process step where issue occurs")
    process_step: Optional[str] = Field(None, min_length=3, max_length=200, description="FMEA: Process step where issue occurs")
    
    issue_type: Optional[str] = Field(None, min_length=5, max_length=200, description="Type of issue/failure")
    failure_mode: Optional[str] = Field(None, min_length=5, max_length=200, description="FMEA: Failure mode")
    
    impact_description: Optional[str] = Field(None, min_length=5, max_length=500, description="Impact/effects of the issue")
    potential_effects: Optional[str] = Field(None, min_length=5, max_length=500, description="FMEA: Potential effects")
    
    severity: int = Field(..., ge=1, le=10, description="Impact severity score (1-10)")
    occurrence: int = Field(..., ge=1, le=10, description="Likelihood score (1-10)")
    detection: int = Field(..., ge=1, le=10, description="Detection ability score (1-10)")
    
    # Optional domain-specific metadata
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Domain-specific additional data")
    
    @field_validator('context_step', 'process_step')
    @classmethod
    def validate_step_field(cls, v, info):
        """Ensure at least one step field is provided."""
        if info.field_name == 'process_step':
            context_step = info.data.get('context_step')
            if not v and not context_step:
                raise ValueError("Either context_step or process_step must be provided")
        return v
    
    @field_validator('issue_type', 'failure_mode')
    @classmethod
    def validate_issue_field(cls, v, info):
        """Ensure at least one issue field is provided."""
        if info.field_name == 'failure_mode':
            issue_type = info.data.get('issue_type')
            if not v and not issue_type:
                raise ValueError("Either issue_type or failure_mode must be provided")
        return v
    
    @field_validator('impact_description', 'potential_effects')
    @classmethod
    def validate_impact_field(cls, v, info):
        """Ensure at least one impact field is provided."""
        if info.field_name == 'potential_effects':
            impact_description = info.data.get('impact_description')
            if not v and not impact_description:
                raise ValueError("Either impact_description or potential_effects must be provided")
        return v
    
    def get_step(self) -> str:
        """Get the step field value (context_step or process_step)."""
        return self.context_step or self.process_step or ""
    
    def get_issue(self) -> str:
        """Get the issue field value (issue_type or failure_mode)."""
        return self.issue_type or self.failure_mode or ""
    
    def get_impact(self) -> str:
        """Get the impact field value (impact_description or potential_effects)."""
        return self.impact_description or self.potential_effects or ""


class RankingConfig(BaseModel):
    """Configuration for ranking behavior - customizable per domain."""
    domain: str = Field(default="generic", description="Domain name (e.g., 'manufacturing', 'software', 'healthcare')")
    weights: RCPSWeights = Field(default_factory=RCPSWeights, description="RCPS calculation weights")
    max_causes: int = Field(default=20, ge=2, le=50, description="Maximum number of causes to rank")
    evidence_context: str = Field(default="investigation", description="Context for evidence evaluation")
    mechanism_context: str = Field(default="technical analysis", description="Context for mechanism evaluation")
    proximity_context: str = Field(default="causal analysis", description="Context for proximity evaluation")


class RankingInput(BaseModel):
    """Input schema for ranking agent - flexible for any domain."""
    causes: List[CauseInput] = Field(..., min_length=2, description="List of candidate causes to rank")
    config: Optional[RankingConfig] = Field(default_factory=RankingConfig, description="Ranking configuration")
    
    @field_validator('causes')
    @classmethod
    def validate_unique_cause_ids(cls, v):
        """Ensure all cause IDs are unique."""
        cause_ids = [cause.cause_id for cause in v]
        if len(cause_ids) != len(set(cause_ids)):
            raise ValueError("All cause_id values must be unique")
        return v
    
    @field_validator('causes')
    @classmethod
    def validate_max_causes(cls, v, info):
        """Validate against configured max causes."""
        if hasattr(info, 'data') and 'config' in info.data:
            max_causes = info.data['config'].max_causes if info.data['config'] else 20
            if len(v) > max_causes:
                raise ValueError(f"Too many causes: {len(v)}. Maximum allowed: {max_causes}")
        return v


class RankedCause(BaseModel):
    """Output schema for a single ranked cause - generic format."""
    rank: int = Field(..., description="Final rank position")
    cause_id: str = Field(..., description="Unique identifier")
    cause_text: str = Field(..., description="Cause description")
    rcps_score: float = Field(..., ge=0.0, le=1.0, description="Root Cause Priority Score (0-1)")
    rpn: int = Field(..., description="Risk Priority Number")
    rpn_score: float = Field(..., description="Normalized RPN score")
    evidence_strength: float = Field(..., description="Evidence strength score")
    mechanism_fit: float = Field(..., description="Mechanism fit score")
    causal_proximity: float = Field(..., description="Causal proximity score")
    risk_level: str = Field(..., description="Risk level: High/Medium/Low")
    justification: str = Field(..., description="Ranking justification")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in ranking")


class RankingOutput(BaseModel):
    """Output schema for ranking agent - generic format."""
    ranked_causes: List[RankedCause] = Field(..., description="All causes ranked by RCPS")
    selected_root_cause: str = Field(..., description="Top ranked cause ID")
    total_causes: int = Field(..., description="Total number of causes evaluated")
    domain: str = Field(..., description="Domain context used for ranking")
    config_used: RankingConfig = Field(..., description="Configuration used for ranking")
    message: str = Field(..., description="Summary message")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional result metadata")


class RankingState(BaseModel):
    """State that flows through the LangGraph nodes - flexible for any domain."""
    input: RankingInput
    rpn_calculated: Optional[List[Dict[str, Any]]] = None
    rpn_normalized: Optional[List[Dict[str, Any]]] = None
    evidence_evaluated: Optional[List[Dict[str, Any]]] = None
    mechanism_evaluated: Optional[List[Dict[str, Any]]] = None
    proximity_evaluated: Optional[List[Dict[str, Any]]] = None
    rcps_calculated: Optional[List[Dict[str, Any]]] = None
    final_output: Optional[RankingOutput] = None
    iteration: int = 0
    error: Optional[str] = None
