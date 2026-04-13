"""
Why Analysis V3 Orchestrator.

Simplified flow with human-in-the-loop:
- question -> causes -> validation -> human_review -> (if 0 causes) zero_evidence

Following risk_analysis_orchestrator_service patterns:
- Payload building in separate payloads.py
- deep_serialize() for all agent results
- Proper tracking IDs (complaint_id, session_id)
- Complete context passing
- Redis checkpointing
"""

from .agent import WhyAnalysisV3Orchestrator
from .orchestrator import orchestrator_graph, deep_serialize, redis_client, _read_state_from_redis
from .router import router
from .schemas import WhyAnalysisV3Input, WhyAnalysisV3Output, HumanReviewInput
from .payloads import build_all_payloads

__all__ = [
    "WhyAnalysisV3Orchestrator",
    "orchestrator_graph",
    "deep_serialize",
    "redis_client",
    "_read_state_from_redis",
    "router",
    "WhyAnalysisV3Input",
    "WhyAnalysisV3Output",
    "HumanReviewInput",
    "build_all_payloads",
]
