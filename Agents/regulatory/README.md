# Regulatory Agent

## What It Does

Evaluates complaints against regulatory policies to determine if regulatory reporting is required, which authorities to notify, reporting deadlines, and CAPA requirements.

## Agent Type

**Policy-Driven Deterministic Agent with LLM Justification**

- Rule matching: Deterministic (no LLM)
- Timeline calculation: Deterministic
- Justification: LLM-generated (AWS Bedrock)

## How It Works

```
Input: Complaint + Policy JSON File Path
  ↓
1. Load Policy (from JSON file in backend)
  ↓
2. Normalize (standardize severity, country, issue_type)
  ↓
3. Evaluate Rules (match complaint fields to rule conditions)
  ↓
4. Select Rule (highest priority if multiple match)
  ↓
5. Calculate Timeline (working/calendar days from awareness date)
  ↓
6. Extract Decision (reportability, authority, CAPA)
  ↓
7. Generate Justification (LLM explains why)
  ↓
Output: Regulatory Decision
```

## Key Features

- **Backend Policy Storage**: Regulatory rules stored in JSON file (not sent with each request)
- **Fully Dynamic**: Accepts any complaint fields (risk_score, batch_number, etc.)
- **Flexible Rules**: Policy conditions can check any field
- **Semantic Matching**: Uses embeddings for description keywords
- **Multiple Authorities**: Collects all authorities from matched rules
- **Real CAPA Regulations**: Includes FDA, EU MDR, UK MHRA, Health Canada rules
- **No Hardcoding**: All decisions from policy, not hardcoded logic

## Architecture

### Backend (Policy Storage)
```
Agents/regulatory/
├── regulatory_policy.json    ← Main policy file (12 real regulations)
├── agent.py                  ← Loads policy from JSON
├── graph.py                  ← LangGraph workflow
├── nodes.py                  ← Processing nodes
└── router.py                 ← FastAPI endpoints
```

### Frontend (Complaint Submission)
- Only sends complaint data
- Optionally sends custom policy path
- Backend handles all policy loading

## Usage

### 1. Initialize Agent (Loads Default Policy)

```python
from Agents.regulatory.agent import RegulatoryAgentLangGraph
from Agents.regulatory.schemas import ComplaintInput

# Initialize agent (automatically loads regulatory_policy.json)
agent = RegulatoryAgentLangGraph()
```

### 2. Process Complaint (Default Policy)

```python
# Create complaint
complaint = ComplaintInput(
    complaint_id="C-2024-001",
    description="Black particles found in sterile vial",
    date_of_awareness="2024-01-15",
    severity="Critical",
    issue_type="Quality Defect",
    distributed_to_market=True,
    market_country="USA",
    patient_risk_level="High"
)

# Process (uses default policy)
result = agent.process_complaint(complaint)

print(f"Reportable: {result['reportable']}")
print(f"Authority: {result['authority']}")
print(f"Due Date: {result['due_date']}")
print(f"CAPA Required: {result['capa_required']}")
```

### 3. Process Complaint (Custom Policy Path)

```python
# Process with custom policy file
result = agent.process_complaint(
    complaint,
    policy_path="/path/to/custom_policy.json"
)
```

### 4. Initialize with Custom Policy

```python
# Initialize with specific policy file
agent = RegulatoryAgentLangGraph(
    policy_path="/path/to/custom_policy.json"
)
```

### 5. Reload Policy at Runtime

```python
# Reload policy from new file
agent.reload_policy("/path/to/new_policy.json")

# Or reload during processing
result = agent.process_complaint(
    complaint,
    policy_path="/path/to/new_policy.json"
)
```

## API Usage

### POST /regulatory/

```bash
POST /regulatory/
Content-Type: application/json

{
  "complaint": {
    "complaint_id": "C-2024-001",
    "description": "Black particles found in sterile vial",
    "date_of_awareness": "2024-01-15",
    "severity": "Critical",
    "issue_type": "Quality Defect",
    "distributed_to_market": true,
    "market_country": "USA"
  },
  "policy_path": "/optional/path/to/policy.json"
}
```

**Response:**
```json
{
  "regulatory_classification": "Quality System - CAPA Required",
  "regulation_reference": "21 CFR 820.100",
  "authority": ["FDA"],
  "reportable": true,
  "report_type": "Field Alert Report",
  "reporting_timeline_days": 10,
  "timeline_type": "Working",
  "due_date": "2024-01-29",
  "capa_required": "Mandatory",
  "compliance_risk_level": "High",
  "matched_rule_id": "FDA-QUALITY-001",
  "justification": "Critical quality defect with contamination requires FDA reporting...",
  "confidence": 0.95
}
```

## Regulatory Policy JSON Format

### File: `regulatory_policy.json`

```json
{
  "regulatory_rules": [
    {
      "rule_id": "FDA-MDR-001",
      "regulation_reference": "21 CFR 803.50",
      "country": "USA",
      "conditions": {
        "distributed_to_market": true,
        "death_or_injury": true,
        "severity": ["Critical"]
      },
      "regulatory_classification": "Medical Device Report - Death/Serious Injury",
      "reportable": true,
      "authority": ["FDA"],
      "report_type": "MDR - 5 Day Report",
      "reporting_timeline_days": 5,
      "timeline_type": "Working",
      "capa_required": "Mandatory",
      "compliance_risk_level": "High"
    }
  ]
}
```

## Included Regulations

The default `regulatory_policy.json` includes:

### FDA (USA)
- **FDA-MDR-001**: Death/Serious Injury (5 working days)
- **FDA-MDR-002**: Device Malfunction (30 calendar days)
- **FDA-QUALITY-001**: Quality/Contamination (10 working days)
- **FDA-RECALL-001**: Class I Recall (24 hours)

### EU MDR
- **EU-MDR-001**: Serious Incident - Immediate (2 working days)
- **EU-MDR-002**: Serious Incident - Follow-up (15 calendar days)

### UK MHRA
- **UK-MHRA-001**: Adverse Incident - Urgent (2 working days)
- **UK-MHRA-002**: Adverse Incident - Standard (10 working days)

### Health Canada
- **CANADA-HC-001**: Mandatory Problem Report - Immediate (10 calendar days)
- **CANADA-HC-002**: Mandatory Problem Report - Standard (30 calendar days)

### Quality Standards
- **ISO-13485-001**: Internal CAPA (30 working days)
- **INTERNAL-001**: Internal Quality Issue (45 working days)

## Input Format

### Required Fields
```json
{
  "complaint_id": "C-2024-001",
  "description": "Detailed complaint description",
  "date_of_awareness": "2024-01-15"
}
```

### Optional Fields
```json
{
  "severity": "Critical",
  "issue_type": "Quality Defect",
  "market_country": "USA",
  "distributed_to_market": true,
  "death_or_injury": false,
  "patient_risk_level": "High",
  "product_type": "Injectable",
  "dosage_form": "Solution"
}
```

### Custom Fields (Any field can be added)
```json
{
  "batch_number": "LOT-2024-001",
  "facility_code": "FAC-US-01",
  "risk_score": 85
}
```

## Output Format

```json
{
  "regulatory_classification": "Medical Device Report",
  "regulation_reference": "21 CFR 803.50",
  "authority": ["FDA"],
  "reportable": true,
  "report_type": "MDR - 30 Day Report",
  "reporting_timeline_days": 30,
  "timeline_type": "Calendar",
  "due_date": "2024-02-14",
  "capa_required": "Mandatory",
  "compliance_risk_level": "High",
  "matched_rule_id": "FDA-MDR-002",
  "justification": "Device malfunction in distributed product requires FDA MDR reporting under 21 CFR 803.50",
  "confidence": 0.95
}
```

## No Policy Behavior

If no policy file exists or is provided:
- Returns `reportable: false`
- Returns `capa_required: "Recommended"` (best practice)
- Provides justification explaining no regulatory match

## Testing

Run the test suite:

```bash
cd Agents/regulatory
python test_regulatory.py
```

Tests include:
1. Default policy usage
2. Custom policy path
3. No policy (non-reportable)
4. Runtime policy reload
5. EU MDR regulations
6. Semantic matching

## Configuration

- **Model**: AWS Bedrock (config/aws_bedrock_config.py)
- **Embeddings**: sentence-transformers (open source)
- **Default Policy**: Agents/regulatory/regulatory_policy.json
- **Logs**: Agents/logs/regulatory.log

## Benefits of This Approach

✅ **Centralized Policy Management**: All regulations in one JSON file  
✅ **Easy Updates**: Modify rules without code changes  
✅ **Version Control**: Track policy changes in git  
✅ **Environment-Specific**: Different policies for dev/staging/prod  
✅ **Lightweight Requests**: Only send complaint data, not entire policy  
✅ **Audit Trail**: Policy file changes are logged  
✅ **Real Regulations**: Based on actual FDA, EU, UK, Canada requirements
