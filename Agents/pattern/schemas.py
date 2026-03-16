from pydantic import BaseModel, Field
from typing import Optional, List, Literal

TrendCategory = Literal[
    "No trend; stable flat data",
    "Minor fluctuation but no upward trend",
    "One short-term spike, not repeated",
    "Weak increasing tendency",
    "Small but noticeable trend signal",
    "Clear visible upward trend",
    "Strong accelerating trend",
    "Recurring trend peaks",
    "Persistent accelerating trend",
    "Uncontrolled exponential trend",
]

class PatternAnalysisRequest(BaseModel):
    """Schema for pattern analysis input"""
    complaint_id: str = Field(..., description="Unique identifier for the current complaint")
    description: str = Field(..., description="Description of the current complaint")
    # Optional contextual attributes for richer multi-attribute analysis
    product_family: Optional[str] = Field(None, description="Product family (e.g. Orthopedic Implant)")
    region: Optional[str] = Field(None, description="Region or country of complaint origin")
    severity: Optional[str] = Field(None, description="Severity level (e.g. Low, Medium, High, Critical)")
    site: Optional[str] = Field(None, description="Manufacturing or distribution site")
class PatternAnalysisResponse(BaseModel):
    """Final response from the Pattern Agent"""

    complaint_id: str = Field(
        ...,
        description="Unique identifier for the complaint"
    )
    trend_score: int = Field(
        ..., ge=1, le=10,
        description="Trend score from 1 to 10"
    )
    trend_category: TrendCategory = Field(
        ...,
        description="Company standard trend category — one of 10 defined values"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence level (0.0-1.0)"
    )
    matched_complaint_ids: List[str] = Field(
        default_factory=list,
        description="List of historical complaint IDs that match the pattern"
    )
    identified_pattern: Optional[str] = Field(
        None,
        description="One-line summary of the identified pattern"
    )
    explanation: str = Field(
        ...,
        description="Detailed explanation of the trend analysis"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if any"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "C-2026-001",
                "trend_score": 8,
                "trend_category": "Recurring trend peaks",
                "confidence": 0.97,
                "matched_complaint_ids": [
                    "NC-112", "NC-116", "NC-129",
                    "NC-139", "NC-148", "NC-183"
                ],
                "identified_pattern": "Recurring Software/Firmware failures in Infusion Pumps across Sites A,B,C,D and 4 regions",
                "explanation": "Six historical records describe software/firmware failures in infusion pumps spanning all 4 sites and 4 regions. All are Critical severity, dual FDA+EU reportable, and marked Repeated. Immediate CAPA escalation and cross-site firmware audit are required.",
                "error": None
            }
        }

    """Final response from the Pattern Agent"""

    complaint_id: str = Field(
        ...,
        description="Unique identifier for the complaint"
    )
    trend_score: int = Field(
        ..., ge=1, le=10,
        description="Trend score from 1 to 10"
    )
    trend_category: str = Field(
        ...,
        description="Category description of the trend"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence level (0.0-1.0)"
    )
    matched_complaint_ids: List[str] = Field(
        default_factory=list,
        description="List of historical complaint IDs that match the pattern"
    )
    identified_pattern: Optional[str] = Field(
        None,
        description="One-line summary of the identified pattern"
    )
    explanation: str = Field(
        ...,
        description="Detailed explanation of the trend analysis"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if any"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "C-2026-001",
                "trend_score": 8,
                "trend_category": "7 or more related records, repeated across multiple sites and regions",
                "confidence": 0.97,
                "matched_complaint_ids": [
                    "NC-112", "NC-116", "NC-129",
                    "NC-139", "NC-148", "NC-183", "NC-192"
                ],
                "identified_pattern": "Recurring Software/Firmware failures in Infusion Pumps across Sites A,B,C,D and 4 regions",
                "explanation": "Seven historical records describe software/firmware failures in infusion pumps spanning all 4 sites and 4 regions. All are Critical severity, dual FDA+EU reportable, and marked Repeated — indicating prior CAPAs failed to resolve the root cause. Immediate CAPA escalation and cross-site firmware audit are required.",
                "error": None
            }
        }