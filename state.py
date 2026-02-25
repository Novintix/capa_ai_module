# Canonical state definition lives in orchestrator_service/state.py
# This file re-exports it to avoid breaking any legacy imports.
from orchestrator_service.state import RiskAssessmentState, AgentResponse

__all__ = ["RiskAssessmentState", "AgentResponse"]
