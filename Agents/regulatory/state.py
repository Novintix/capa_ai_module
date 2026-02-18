"""
Regulatory Agent State Definition
Structured state for Regulatory Agent using TypedDict.
"""

from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict, total=False):
    """
    Structured state for Regulatory Agent.
    All fields are optional to allow flexible complaint inputs.
    """
    # Input - Complaint Data (Core fields)
    complaint_id: str
    description: str
    date_of_awareness: str
    
    # Input - Complaint Data (Common optional fields)
    product_type: Optional[str]
    dosage_form: Optional[str]
    market_country: Optional[str]
    severity: Optional[str]
    issue_type: Optional[str]
    distributed_to_market: Optional[bool]
    death_or_injury: Optional[bool]
    patient_risk_level: Optional[str]
    
    # Input - Risk/Score fields (for risk-based policies)
    risk_score: Optional[int]
    severity_score: Optional[int]
    occurrence_score: Optional[int]
    detection_score: Optional[int]
    
    # Input - Custom fields (add more as needed)
    batch_number: Optional[str]
    facility_code: Optional[str]
    product_line: Optional[str]
    
    # Input - Policy Data
    regulatory_rules: Optional[List[Dict]]
    
    # Intermediate - Normalized Data
    normalized_severity: Optional[str]
    normalized_issue_type: Optional[str]
    normalized_country: Optional[str]
    
    # Intermediate - Rule Matching
    matched_rules: Optional[List[Dict]]
    selected_rule: Optional[Dict]
    
    # Output - Regulatory Decision
    regulatory_classification: Optional[str]
    regulation_reference: Optional[str]
    authority: Optional[List[str]]
    reportable: Optional[bool]
    report_type: Optional[str]
    reporting_timeline_days: Optional[int]
    timeline_type: Optional[str]
    due_date: Optional[str]
    capa_required: Optional[str]
    compliance_risk_level: Optional[str]
    matched_rule_id: Optional[str]
    justification: Optional[str]
    confidence: Optional[float]
    
    # Control
    iteration: int
    max_iterations: int
    error: Optional[str]
    next_step: Optional[str]
