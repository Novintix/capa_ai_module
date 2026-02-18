"""
Regulatory Agent Data Schemas
Defines the structure of input and output data.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ComplaintInput(BaseModel):
    """Schema for complaint data input - generalized with minimal required fields"""
    
    # Mandatory fields
    complaint_id: str = Field(..., description="Unique identifier for the complaint")
    description: str = Field(..., description="Detailed description of the complaint")
    date_of_awareness: str = Field(..., description="Date when issue was identified (YYYY-MM-DD)")
    
    # Optional fields - agent will work with any combination
    product_type: Optional[str] = Field(None, description="Type of product")
    dosage_form: Optional[str] = Field(None, description="Dosage form of the product")
    market_country: Optional[str] = Field(None, description="Country where product is marketed")
    severity: Optional[str] = Field(None, description="Severity level of the complaint")
    issue_type: Optional[str] = Field(None, description="Type of issue reported")
    distributed_to_market: Optional[bool] = Field(None, description="Whether product was distributed to market")
    death_or_injury: Optional[bool] = Field(None, description="Whether death or injury occurred")
    patient_risk_level: Optional[str] = Field(None, description="Level of patient risk")
    
    # Allow any additional fields
    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "complaint_id": "C-2024-001",
                "description": "Contamination detected in batch",
                "date_of_awareness": "2024-01-15",
                "severity": "Critical",
                "distributed_to_market": True
            }
        }


class RegulatoryRule(BaseModel):
    """Schema for a single regulatory rule - fully flexible"""
    
    rule_id: str = Field(..., description="Unique rule identifier")
    regulation_reference: str = Field(..., description="Reference to regulation")
    country: str = Field(..., description="Country this rule applies to")
    conditions: dict = Field(..., description="Conditions that must be met (any fields)")
    regulatory_classification: str = Field(..., description="Classification of the regulatory requirement")
    reportable: bool = Field(..., description="Whether this requires reporting")
    authority: List[str] = Field(default_factory=list, description="Regulatory authorities")
    report_type: str = Field(..., description="Type of report required")
    reporting_timeline_days: int = Field(..., description="Days to report")
    timeline_type: str = Field(..., description="Type of timeline (Working/Calendar/Hours)")
    capa_required: str = Field(..., description="CAPA requirement (Mandatory/Recommended/No)")
    compliance_risk_level: str = Field(..., description="Risk level (Low/Medium/High)")
    
    # Allow any additional fields
    class Config:
        extra = "allow"


class RegulatoryPolicy(BaseModel):
    """Schema for regulatory policy input"""
    
    regulatory_rules: List[RegulatoryRule] = Field(..., description="List of regulatory rules")
    
    class Config:
        json_schema_extra = {
            "example": {
                "regulatory_rules": [
                    {
                        "rule_id": "FDA-001",
                        "regulation_reference": "21 CFR 803",
                        "country": "USA",
                        "conditions": {
                            "distributed_to_market": True,
                            "issue_type": "Quality Defect",
                            "severity": ["Critical", "Major"],
                            "patient_risk_level": ["High", "Medium"]
                        },
                        "regulatory_classification": "Medical Device Report",
                        "reportable": True,
                        "authority": ["FDA"],
                        "report_type": "MDR",
                        "reporting_timeline_days": 30,
                        "timeline_type": "Calendar",
                        "capa_required": "Mandatory",
                        "compliance_risk_level": "High"
                    }
                ]
            }
        }


class RegulatoryDecision(BaseModel):
    """Schema for regulatory decision output"""
    
    regulatory_classification: str = Field(..., description="Classification of regulatory requirement")
    regulation_reference: str = Field(..., description="Reference to regulation")
    authority: List[str] = Field(default_factory=list, description="Regulatory authorities")
    reportable: bool = Field(..., description="Whether reporting is required")
    report_type: str = Field(..., description="Type of report required")
    reporting_timeline_days: int = Field(..., description="Days to report")
    timeline_type: str = Field(..., description="Type of timeline")
    due_date: str = Field(..., description="Calculated due date (YYYY-MM-DD)")
    capa_required: str = Field(..., description="CAPA requirement")
    compliance_risk_level: str = Field(..., description="Risk level")
    matched_rule_id: str = Field(..., description="ID of matched rule")
    justification: str = Field(..., description="Explanation of decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level (0.0-1.0)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "regulatory_classification": "Medical Device Report",
                "regulation_reference": "21 CFR 803",
                "authority": ["FDA"],
                "reportable": True,
                "report_type": "MDR",
                "reporting_timeline_days": 30,
                "timeline_type": "Calendar",
                "due_date": "2024-02-14",
                "capa_required": "Mandatory",
                "compliance_risk_level": "High",
                "matched_rule_id": "FDA-001",
                "justification": "Critical quality defect in distributed product requires FDA reporting",
                "confidence": 0.95
            }
        }
