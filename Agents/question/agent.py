"""
Why Question Agent
Main agent class that drives the LangGraph workflow with Redis-backed memory.

Session lifecycle:
  POST /why/start    — First Why. Accepts full context, stores in Redis under complaint_id.
  POST /why/continue — Subsequent Whys. Only needs complaint_id + answer; everything
                        else is loaded from Redis.

Redis TTL: 7 days (604800 seconds). After expiry the chain must be restarted.
"""

import os
from typing import Dict, Any

from langgraph.checkpoint.redis import RedisSaver

from .graph import create_why_question_graph
from .state import AgentState
from .schemas import StartWhyInput, ContinueWhyInput
from .logger import log_error
from config.aws_bedrock_config import get_llm
from agent_ops import agentops_agent, agentops_operation


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# langgraph-checkpoint-redis v0.4.x interprets default_ttl as MINUTES
REDIS_TTL_MINUTES = 7 * 24 * 60  # 7 days = 10080 minutes


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

@agentops_agent(name="why_question_agent")
class WhyQuestionAgent:
    """
    Why Question Agent using LangGraph + Redis checkpointer.

    Each CAPA complaint gets its own Redis-backed session keyed by complaint_id.
    The full context (complaint, evidence, SOP, prior chain) is persisted automatically
    so callers only need to supply complaint_id + answer on subsequent Why calls.
    """

    def __init__(self):
        """Initialize Bedrock LLM, Redis checkpointer, and compile the graph."""
        try:
            get_llm()
        except Exception as exc:
            raise ValueError(f"AWS Bedrock initialization failed: {exc}") from exc

        try:
            self.checkpointer = RedisSaver(
                redis_url=REDIS_URL,
                ttl={"default_ttl": REDIS_TTL_MINUTES}
            )
            self.checkpointer.setup()
        except Exception as exc:
            raise ValueError(f"Redis initialization failed: {exc}") from exc

        self.graph = create_why_question_graph(checkpointer=self.checkpointer)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    @agentops_operation(name="start")
    def start(self, input_data: StartWhyInput) -> Dict[str, Any]:
        """
        Start a new Why chain for a complaint.

        Stores complaint, evidence, and SOP in Redis under complaint_id.
        Returns the first Why question.
        """
        initial_state: AgentState = {
            # Inputs
            "complaint_id": input_data.complaint_id,
            "complaint": input_data.complaint,
            "evidence": input_data.evidence,
            "sop": input_data.sop,
            "previous_why": [],
            "previous_answers": [],
            # Intermediates
            "why_depth": None,
            "validated": False,
            # Outputs
            "why_question": None,
            "reasoning": None,
            # Control
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
            "next_step": None
        }

        config = {"configurable": {"thread_id": input_data.complaint_id}}
        final_state = self.graph.invoke(initial_state, config=config)
        return self._build_result(final_state)

    @agentops_operation(name="continue_chain")
    def continue_chain(self, input_data: ContinueWhyInput) -> Dict[str, Any]:
        """
        Continue an existing Why chain.

        Loads the last saved state from Redis using complaint_id,
        appends the new answer, and generates the next Why question.
        """
        config = {"configurable": {"thread_id": input_data.complaint_id}}

        # Load last checkpoint from Redis
        saved = self.graph.get_state(config)
        if not saved.values:
            raise ValueError(
                f"No active Why chain found for complaint_id '{input_data.complaint_id}'. "
                f"Please call /why/start first."
            )

        last = saved.values

        # Build updated chain: append the last generated question + new answer
        previous_why = list(last.get("previous_why") or [])
        previous_answers = list(last.get("previous_answers") or [])

        last_why_question = last.get("why_question")
        if last_why_question:
            previous_why.append(last_why_question)
        previous_answers.append(input_data.answer)

        # New invocation state — complaint/evidence/sop come from Redis
        new_state: AgentState = {
            "complaint_id": input_data.complaint_id,
            "complaint": last["complaint"],
            "evidence": last["evidence"],
            "sop": last["sop"],
            "previous_why": previous_why,
            "previous_answers": previous_answers,
            "why_depth": None,
            "validated": False,
            "why_question": None,
            "reasoning": None,
            "iteration": 0,
            "max_iterations": 5,
            "error": None,
            "next_step": None
        }

        final_state = self.graph.invoke(new_state, config=config)
        return self._build_result(final_state)

    @agentops_operation(name="get_history")
    def get_history(self, complaint_id: str) -> Dict[str, Any]:
        """
        Retrieve the full Q&A history for a complaint's Why chain from Redis.

        Returns all answered Why questions plus the latest pending question
        (if one exists but hasn't been answered yet).
        """
        config = {"configurable": {"thread_id": complaint_id}}
        saved = self.graph.get_state(config)

        if not saved.values:
            raise ValueError(
                f"No Why chain found for complaint_id '{complaint_id}'. "
                f"Please call /why/start first."
            )

        state = saved.values
        previous_why = list(state.get("previous_why") or [])
        previous_answers = list(state.get("previous_answers") or [])
        latest_question = state.get("why_question")

        # Build the interleaved chain
        # previous_why[i] was answered by previous_answers[i]
        # latest_question is the most recently generated question (unanswered)
        chain = []
        for i, question in enumerate(previous_why):
            chain.append({
                "depth": i + 1,
                "question": question,
                "answer": previous_answers[i] if i < len(previous_answers) else None
            })

        # Append the latest generated question as the pending (unanswered) entry
        if latest_question:
            chain.append({
                "depth": len(previous_why) + 1,
                "question": latest_question,
                "answer": None
            })

        return {
            "complaint_id": complaint_id,
            "complaint": state.get("complaint", ""),
            "total_whys": len(chain),
            "chain": chain
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(state: dict) -> Dict[str, Any]:
        return {
            "complaint_id": state.get("complaint_id"),
            "why_question": state.get("why_question"),
            "reasoning": state.get("reasoning"),
            "why_depth": state.get("why_depth"),
            "error": state.get("error")
        }
