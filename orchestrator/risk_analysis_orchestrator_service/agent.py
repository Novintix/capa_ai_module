"""
risk_analysis_orchestrator_service/agent.py

Risk Analysis Orchestrator Agent (O2)

Wrapper class that follows the same pattern as fishbone_v3/agent.py and
why_analysis_v3/agent.py, providing AgentOps tracing for the full Risk
Analysis pipeline.

AgentOps span hierarchy created:
    AGENT  : risk_analysis_v3_orchestrator
      └── OPERATION : analyze
      └── OPERATION : correct_input
      └── OPERATION : resume
"""

import uuid
from typing import Any, Dict, Optional

from .orchestrator import orchestrator_graph, deep_serialize, MAX_CORRECTION_ATTEMPTS
from agent_ops import agentops_agent, agentops_operation


@agentops_agent(name="risk_analysis")
class RiskAnalysisOrchestratorAgent:
    """
    Risk Analysis Orchestrator Agent — AgentOps-traced wrapper.

    Delegates to the compiled LangGraph orchestrator_graph while exposing
    each public action as an @agentops_operation so every run is fully
    visible in the AgentOps dashboard.
    """

    def __init__(self):
        self.graph = orchestrator_graph

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    @agentops_operation(name="analyze")
    def analyze(
        self,
        raw_input: Optional[str] = None,
        enriched_input: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None,
        complaint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run full risk analysis on a complaint.

        Args:
            raw_input: Free-text complaint description.
            enriched_input: Structured complaint fields from the UI (skips LLM extraction).
            thread_id: Optional thread ID for Redis checkpointing.
            complaint_id: Optional complaint ID to embed in initial state.

        Returns:
            Final orchestrator state dict (deep-serialized).
        """
        thread_id = thread_id or f"capa-{uuid.uuid4().hex[:12]}"
        config = self._config(thread_id)

        initial_state: Dict[str, Any] = {
            "thread_id":        thread_id,
            "raw_input":        raw_input or "",
            "agent_results":    [],
            "node_log":         [],
            "errors":           [],
            "correction_count": 0,
        }
        if complaint_id:
            initial_state["complaint_id"] = complaint_id
        if enriched_input:
            initial_state["enriched_input"] = enriched_input

        result = self.graph.invoke(initial_state, config=config)
        return deep_serialize(result)

    @agentops_operation(name="correct_input")
    def correct_input(
        self,
        thread_id: str,
        corrected_input: str,
    ) -> Dict[str, Any]:
        """
        Submit corrected input after a validation failure.

        Patches `raw_input` in the last checkpoint and re-runs from
        `input_validator` with the correction counter preserved.

        Args:
            thread_id: Thread ID of the paused workflow.
            corrected_input: New complaint description to validate.

        Returns:
            Final orchestrator state dict (deep-serialized).
        """
        config = self._config(thread_id)

        self.graph.update_state(
            config,
            {
                "raw_input":           corrected_input,
                "awaiting_correction": False,
                "correction_response": None,
                "correction_message":  None,
            },
            as_node="input_validator",
        )

        result = self.graph.invoke(None, config=config)
        return deep_serialize(result)

    @agentops_operation(name="resume")
    def resume(
        self,
        thread_id: str,
        state_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resume a paused or crashed workflow from the last Redis checkpoint.

        Args:
            thread_id: Thread ID of the workflow to resume.
            state_patch: Optional state patch to inject before resuming.

        Returns:
            Final orchestrator state dict (deep-serialized).
        """
        config = self._config(thread_id)

        if state_patch:
            self.graph.update_state(config, state_patch)

        result = self.graph.invoke(None, config=config)
        return deep_serialize(result)
