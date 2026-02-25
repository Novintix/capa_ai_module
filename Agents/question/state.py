"""
Agent State Definition
Structured state for Why Question Agent using TypedDict.
"""

from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    """
    Structured state for Why Question Agent.
    Every field is explicitly defined.
    """
    # -------------------------------------------------------------------------
    # Input fields
    # -------------------------------------------------------------------------
    complaint_id: str       # Unique identifier — used as the Redis thread key throughout the chain
    complaint: str          # The original complaint / problem statement (stays constant throughout the chain)
    evidence: str           # Supporting facts, observations, data
    sop: str                # Standard Operating Procedure / work instruction
    previous_why: Optional[List[str]]       # Ordered list of "Why" questions already asked
    previous_answers: Optional[List[str]]   # Ordered list of answers to those "Why" questions

    # -------------------------------------------------------------------------
    # Intermediate fields
    # -------------------------------------------------------------------------
    why_depth: Optional[int]            # Depth level of the question being generated
    validated: bool                     # Whether the inputs passed validation

    # -------------------------------------------------------------------------
    # Output fields
    # -------------------------------------------------------------------------
    why_question: Optional[str]         # The generated "Why?" question
    reasoning: Optional[str]            # Agent's reasoning for choosing this question

    # -------------------------------------------------------------------------
    # Control fields
    # -------------------------------------------------------------------------
    iteration: int
    max_iterations: int
    error: Optional[str]
    next_step: Optional[str]
