"""
Data Schemas
Defines the structure of input and output data for the Why Question Agent.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class StartWhyInput(BaseModel):
    """
    Schema for the FIRST Why in an analysis chain.
    Provides full context — stored in Redis under complaint_id.
    """

    complaint_id: str = Field(
        ...,
        description="Unique identifier for the complaint/CAPA record. Used as the Redis session key."
    )
    complaint: str = Field(
        ...,
        description=(
            "The original complaint or problem statement. "
            "Stored in Redis and reused for every subsequent Why in this chain."
        )
    )
    evidence: str = Field(
        ...,
        description="Supporting facts, observations, measurements, or data relevant to the problem."
    )
    sop: str = Field(
        ...,
        description=(
            "Standard Operating Procedure, work instruction, or process guideline "
            "relevant to the problem context."
        )
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "CAPA-2026-001",
                "complaint": "The sealing machine produced defective seals during the night shift.",
                "evidence": (
                    "Seal failure rate was 12% vs the normal 0.5%. "
                    "Temperature logs show sealing bar reached only 160\u00b0C instead of 180\u00b0C."
                ),
                "sop": (
                    "SOP-SEAL-004: Sealing bar must be pre-heated to 180\u00b0C \u00b12\u00b0C for at least "
                    "15 minutes before production begins. Operator must verify temperature "
                    "on the calibrated display before starting the line."
                )
            }
        }


class ContinueWhyInput(BaseModel):
    """
    Schema for the 2nd and subsequent Whys in an analysis chain.
    Only requires complaint_id + the answer to the previously asked Why.
    All other context is loaded from Redis.
    """

    complaint_id: str = Field(
        ...,
        description="The complaint_id used in the original /why/start call."
    )
    answer: str = Field(
        ...,
        description="The answer to the Why question that was last generated for this complaint."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "CAPA-2026-001",
                "answer": "The pre-heat timer was never started by the night shift operator."
            }
        }


class WhyQuestionOutput(BaseModel):
    """Schema for why-question generation output."""

    complaint_id: str = Field(..., description="The complaint ID this question belongs to.")
    why_question: str = Field(
        ...,
        description="The generated 'Why?' question to ask next in the analysis chain."
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of why this question advances the root cause analysis."
    )
    why_depth: int = Field(
        ...,
        ge=1,
        description="Depth level of this question in the 5 Whys chain (1 = first Why)."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "CAPA-2026-001",
                "why_question": "Why did the sealing bar not reach the required 180\u00b0C temperature before production started?",
                "reasoning": (
                    "The evidence directly identifies the temperature shortfall as the proximate cause. "
                    "The SOP mandates a 15-minute pre-heat, so the question probes whether that step was skipped or failed."
                ),
                "why_depth": 1
            }
        }


class WhyQuestionError(BaseModel):
    """Schema for errors returned by the Why Question Agent."""

    error_type: str = Field(..., description="Type of error encountered.")
    error_message: str = Field(..., description="Detailed error message.")

    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "missing_input",
                "error_message": "The 'evidence' field is required and cannot be empty."
            }
        }


class WhyChainEntry(BaseModel):
    """A single Why question + its answer in the chain."""

    depth: int = Field(..., ge=1, description="Position in the chain (1 = first Why).")
    question: str = Field(..., description="The Why question asked at this depth.")
    answer: Optional[str] = Field(
        default=None,
        description="The answer provided for this Why. None if not yet answered."
    )


class WhyChainHistoryOutput(BaseModel):
    """Full Q&A history for a complaint's 5 Whys chain."""

    complaint_id: str = Field(..., description="The complaint ID this chain belongs to.")
    complaint: str = Field(..., description="The original complaint / problem statement.")
    total_whys: int = Field(..., description="Total number of Why questions generated so far.")
    chain: List[WhyChainEntry] = Field(
        ...,
        description="Ordered list of Why questions and their answers (oldest first)."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "CAPA-2026-001",
                "complaint": "The sealing machine produced defective seals during the night shift.",
                "total_whys": 2,
                "chain": [
                    {
                        "depth": 1,
                        "question": "Why did the sealing bar not reach 180\u00b0C before production started?",
                        "answer": "The pre-heat timer was never started by the night shift operator."
                    },
                    {
                        "depth": 2,
                        "question": "Why was the pre-heat timer not started?",
                        "answer": None
                    }
                ]
            }
        }
