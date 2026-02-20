# AI Reasoning Agent

## Overview

The AI Reasoning Agent generates comprehensive reasoning and recommendations based on risk assessment inputs. It analyzes risk scores, patterns, severity levels, and various impacts to provide actionable insights.

## Input Parameters

### Required Fields
- **complaint_id**: Unique identifier for the complaint
- **risk_score**: Overall risk score (1-100)
- **pattern**: Pattern identified from occurrence analysis
- **severity_level**: Severity level (Critical, High, Medium, Low)
- **nc_source**: Non-conformance source
- **regulatory_impact**: Description of regulatory implications
- **customer_impact**: Description of customer impact

### Optional Fields
- **additional_context**: Optional additional context
- **additional_data_json**: JSON string containing ANY additional data fields (flexible schema)

## Flexible Schema - additional_data_json

The agent accepts ANY additional data through the `additional_data_json` parameter. This allows for future extensibility without code changes.

### Example additional_data_json:

```json
{
  "occurrence_score": 8,
  "detection_score": 6,
  "severity_score": 9,
  "historical_data": "5 similar incidents in past 6 months",
  "root_cause": "Tooling wear on Assembly Line 3",
  "capa_status": "Previous CAPA 60% effective",
  "process_capability": "Cpk = 1.15",
  "affected_lot_numbers": ["LOT-123", "LOT-145"],
  "customer_complaints": 12,
  "field_failures": 3,
  "warranty_claims": 8,
  "estimated_cost_impact": "$250,000",
  "supplier_info": "Supplier XYZ - Quality audit score 85/100",
  "environmental_factors": "Temperature variation noted",
  "any_future_field": "any value"
}
```

## Output

The agent returns:
- **reasoning**: Comprehensive explanation of the risk assessment
- **key_factors**: List of key contributing factors
- **recommendations**: List of actionable recommendations
- **confidence_level**: Assessment confidence (High/Medium/Low)


## Architecture

The agent follows a 3-node graph structure:

1. **prepare_evidence**: Builds structured evidence summary from inputs (including all additional_data)
2. **generate_reasoning**: Calls LLM to generate AI reasoning
3. **finalize_output**: Validates and returns final output

## API Endpoint

```
POST /aireasoning/analyze
```

### Example Request (Minimal Data)

```bash
curl -X POST "http://localhost:8000/aireasoning/analyze" \
  -F "complaint_id=C12345" \
  -F "risk_score=75" \
  -F "pattern=Recurring defect" \
  -F "severity_level=High" \
  -F "nc_source=Manufacturing" \
  -F "regulatory_impact=FDA reporting required" \
  -F "customer_impact=Recall possible"
```

### Example Request (Comprehensive Data)

```bash
curl -X POST "http://localhost:8000/aireasoning/analyze" \
  -F "complaint_id=C12345" \
  -F "risk_score=75" \
  -F "pattern=Recurring defect in assembly process" \
  -F "severity_level=High" \
  -F "nc_source=Manufacturing - Assembly Line 3" \
  -F "regulatory_impact=Potential FDA reporting required" \
  -F "customer_impact=Product recall possible. 500 units affected" \
  -F 'additional_data_json={"occurrence_score":8,"detection_score":6,"severity_score":9,"historical_data":"5 similar incidents","root_cause":"Tooling wear","capa_status":"Previous CAPA 60% effective","process_capability":"Cpk = 1.15"}'
```

### Example Response

```json
{
  "reasoning": "The risk score of 75/100 indicates a critical risk level driven by recurring assembly defects with high severity...",
  "key_factors": [
    "Recurring pattern indicates systemic process failure",
    "High severity level with regulatory reporting obligations",
    "Significant customer impact with potential recall scenario"
  ],
  "recommendations": [
    "Initiate immediate root cause analysis of assembly process",
    "Implement enhanced quality controls and monitoring",
    "Prepare regulatory notification documentation"
  ],
  "confidence_level": "High"
}
```

## Logging

All agent activities are logged to `Agents/logs/aireasoning.log` in append mode including:
- Node execution flow
- Prompts sent to LLM
- Raw LLM responses
- Final outputs with justification scores
- Errors and exceptions

Logs persist across multiple requests and are never overwritten.

## Future Extensibility

The flexible `additional_data_json` schema means:
- ✅ No code changes needed for new data fields
- ✅ Any system can send custom data
- ✅ Forward compatible with future requirements
- ✅ Easy integration with other agents (occurrence, severity, detection)

## Test Date

February 19, 2026
