"""
Data Schemas
Defines the structure of input and output data.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ComplaintData(BaseModel):
    """Schema for complaint data input"""
    
    complaint_id: str = Field(..., description="Unique identifier for the complaint")
    source: str = Field(..., description="Source or location where defect was detected")
    description: str = Field(..., description="Detailed description of the issue or defect")
    severity: Optional[str] = Field(None, description="Severity level of the complaint")
    region: Optional[str] = Field(None, description="Geographic region")
    product_family: Optional[str] = Field(None, description="Product family or category")
    site: Optional[str] = Field(None, description="Site or facility location")
    
    class Config:
        json_schema_extra = {
            "example": {
                "complaint_id": "C-001",
                "source": "Service Report",
                "description": "Seal integrity failure observed after sterilization",
                "severity": "Medium",
                "region": "USA",
                "product_family": "Medical Device",
                "site": "Site A"
            }
        }


class DetectionScore(BaseModel):
    """Schema for detection score output"""
    
    detection_score: int = Field(..., ge=1, le=10, description="Calculated detection score (1-10)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level of the score (0.0-1.0)")
    rule_reference: str = Field(..., description="Reference to the policy rule used")
    explanation: str = Field(..., description="Human-readable explanation of the score")
    decision_source: str = Field(..., description="Source of the decision (policy/default/error)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detection_score": 9,
                "confidence": 0.95,
                "rule_reference": "Policy Rule #2: Customer Detection",
                "explanation": "Defect detected by customer via service report after product delivery",
                "decision_source": "policy"
            }
        }


class ScoringError(BaseModel):
    """Schema for scoring errors"""
    
    error_type: str = Field(..., description="Type of error encountered")
    error_message: str = Field(..., description="Detailed error message")
    fallback_score: Optional[int] = Field(None, description="Fallback score if applicable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "insufficient_data",
                "error_message": "Policy document does not contain detection scoring rules",
                "fallback_score": 10
            }
        }
