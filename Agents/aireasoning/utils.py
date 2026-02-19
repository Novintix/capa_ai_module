from Agents.aireasoning.prompts import AI_REASONING_PROMPT_TEMPLATE
from typing import Optional, Dict, Any


def build_evidence_summary(
    risk_score: int,
    pattern: str,
    severity_level: str,
    nc_source: str,
    regulatory_impact: str,
    customer_impact: str,
    additional_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Builds a structured evidence summary from input parameters.
    Accepts any additional data dynamically through additional_data dict.
    """
    evidence = f"""
**Risk Score Analysis**: {risk_score}/100 indicates {"critical" if risk_score >= 70 else "high" if risk_score >= 50 else "moderate" if risk_score >= 30 else "low"} risk level

**Pattern Identified**: {pattern}

**Severity Assessment**: {severity_level} severity level

**Source Analysis**: Non-conformance originated from {nc_source}

**Regulatory Considerations**: {regulatory_impact}

**Customer Impact**: {customer_impact}
"""
    
    # Add any additional data dynamically
    if additional_data:
        evidence += "\n\n**Additional Evidence**:"
        for key, value in additional_data.items():
            # Format the key to be more readable (convert snake_case to Title Case)
            formatted_key = key.replace('_', ' ').title()
            
            # Handle different value types
            if isinstance(value, (list, dict)):
                import json
                evidence += f"\n- {formatted_key}: {json.dumps(value, indent=2)}"
            else:
                evidence += f"\n- {formatted_key}: {value}"
    
    return evidence.strip()


def build_prompt(
    complaint_id: str,
    risk_score: int,
    pattern: str,
    severity_level: str,
    nc_source: str,
    regulatory_impact: str,
    customer_impact: str,
    additional_context: str,
    evidence_summary: str
) -> str:
    """
    Builds the complete prompt for the AI reasoning agent.
    """
    return AI_REASONING_PROMPT_TEMPLATE.format(
        complaint_id=complaint_id,
        risk_score=risk_score,
        pattern=pattern,
        severity_level=severity_level,
        nc_source=nc_source,
        regulatory_impact=regulatory_impact,
        customer_impact=customer_impact,
        additional_context=additional_context,
        evidence_summary=evidence_summary
    )
