# 🏥 CAPA Occurrence Agent

An advanced AI-driven risk assessment module designed to analyze medical device complaints and determine a deterministic **Occurrence Rating (1-10)** using LangGraph and AWS Bedrock. Now supports structured pattern analysis and similar cases data.

---

## 🆕 New Features

### Enhanced Input Support
- **Pattern Analysis Integration**: Accepts structured pattern analysis results with trend scoring and matched complaint IDs
- **Similar Cases Data**: Processes structured similar cases analysis with similarity scores and detailed case information
- **Backward Compatibility**: Maintains support for legacy similar cases format
- **Multi-format Processing**: Automatically detects and processes different input formats

### Structured Data Models
- `PatternData`: Handles pattern analysis results with trend categories, confidence scores, and matched complaints
- `SimilarCasesData`: Processes similar cases with detailed metadata including severity, CAPA requirements, and workflow stages
- Enhanced evidence building that prioritizes pattern data for trend analysis parameters

---

## 📋 Input Formats

### New Structured Format

#### Pattern Data
```json
{
  "complaint_id": "C-2026-002",
  "trend_score": 10,
  "trend_category": "Uncontrolled exponential trend",
  "confidence": 0.97,
  "matched_complaint_ids": ["NC-154", "NC-141", "NC-137"],
  "identified_pattern": "Surface Defect in Orthopedic Implant across multiple sites",
  "explanation": "Detailed pattern explanation...",
  "error": null
}
```

#### Similar Cases Data
```json
{
  "query": "device overheating, burn marks on casing",
  "similarityThreshold": 0.7,
  "similarCount": 2,
  "message": "Found 2 similar case(s) above the 70% similarity threshold.",
  "topMatches": [
    {
      "recordId": "NC 042-0042",
      "complaintId": "NC 042",
      "dateReceived": "2025-08-30T00:00:00",
      "source": "Supplier Audit",
      "severity": "Low",
      "productFamily": "Stent",
      "site": "Site A",
      "descriptionOfIssue": "Overheating issue during device sterilization cycle",
      "capaNeeded": false,
      "similarity": 0.7508
    }
  ]
}
```

### Legacy Format (Still Supported)
```json
[
  {
    "case_id": "NC-042",
    "similarity_score": 0.75,
    "occurrence_factors": {
      "Historical Frequency of Events": "Low frequency, isolated incidents",
      "Trend Analysis / Pattern Recognition": "No clear trend identified"
    }
  }
]
```

---

## 🛡️ Enhanced Evidence Processing

### Pattern-Driven Evidence
- **Trend Analysis (TR)**: Prioritizes pattern data for trend scoring with confidence levels
- **Historical Frequency (HF)**: Uses matched complaint counts from pattern analysis
- **Systemic Risk (SY)**: Leverages pattern scope across sites and regions

### Smart Field Mapping
- Automatically maps new similar cases fields to occurrence parameters
- Handles CAPA requirements, detection times, and site-specific issues
- Maintains backward compatibility with legacy occurrence_factors format

---

## �️ System Architecture

The agent follows a **Linear Stateful Orchestration** pattern, strictly separating data preprocessing, AI-driven classification, and mathematical normalization.

### 🔄 Execution Flow
```text
[ API REQUEST ] ──────▶ [ INPUT VALIDATION ] ────┐
                                                │
    ┌───────────────────────────────────────────┘
    │
    ▼
[ NODE: PREPARE EVIDENCE ]  ──▶ ( Deterministic Merge & Conflict Resolution )
    │
    ▼
[ NODE: GENERATE SCORES  ]  ──▶ ( Evidence-First Anchoring via LLM )
    │
    ▼
[ NODE: WEIGHTED CALC ]     ──▶ ( Mathematical Clamping & Rounding )
    │
    └───────────────────────────────────────────┐
                                                │
[ API RESPONSE ] ◀──────────────────────────────┘
```

---

## 📋 Core Components

### Input Validation
*   **Responsibility**: Guard the graph from malformed payloads.
*   **Methodology**: Pydantic Schema Enforcement.

### Prepare Evidence (Node 1)
*   **Responsibility**: Resolve conflicting historical data.
*   **Methodology**: Python Similarity-Based Merging (Deterministic).

### Generate Scores (Node 2)
*   **Responsibility**: Match evidence to the CAPA Rubric.
*   **Methodology**: LLM (Claude 3.5 Sonnet) with Evidence-First Anchoring.

### Weighted Calculation (Node 3)
*   **Responsibility**: Normalize factor breakdown into final rating.
*   **Methodology**: Weighted Sum Algorithm (Clamped 1-10).

---

---

## 🚀 Usage Examples

### Using the Agent Class
```python
from Agents.occurrence.agent import OccurrenceAgent

agent = OccurrenceAgent()

# With pattern and similar cases data
result = agent.analyze_with_pattern_and_similar_cases(
    complaint_id="C-2026-002",
    description="Surface defect on orthopedic implant",
    source="Quality Control",
    date="2026-03-16",
    product="Orthopedic Implant - Hip Joint",
    pattern_data=pattern_data_dict,
    similar_cases_data=similar_cases_dict
)

print(f"Occurrence Score: {result.weighted_score}/10")
print(f"Rating: {result.rating}")
```

### Using the API Endpoint
```bash
curl -X POST "http://localhost:8000/occurrence/analyze" \
  -F "complaint_id=C-2026-002" \
  -F "description=Surface defect on orthopedic implant" \
  -F "source=Quality Control" \
  -F "date=2026-03-16" \
  -F "product=Orthopedic Implant" \
  -F "pattern_data_json={\"complaint_id\":\"C-2026-002\",\"trend_score\":10,...}" \
  -F "similar_cases_data_json={\"query\":\"surface defect\",\"topMatches\":[...]}"
```

### Convenience Function
```python
from Agents.occurrence.agent import analyze_occurrence

# Automatic format detection
result = analyze_occurrence(
    complaint_id="C-2026-002",
    description="Surface defect on orthopedic implant",
    source="Quality Control",
    date="2026-03-16",
    product="Orthopedic Implant",
    pattern_data=pattern_data,  # New format
    similar_cases_data=similar_cases_data  # New format
)
```

---

## 🧪 Testing

Run the test script to verify functionality:
```bash
python Agents/occurrence/test_new_format.py
```

This tests both the new structured format and backward compatibility with legacy format.

---

## 📥 Input & Output Formats

### API Endpoint Input (Form Data)

**Endpoint:** `POST /occurrence/analyze`

#### Required Fields
```
complaint_id: str           # Unique complaint identifier (e.g., "C-2026-002")
description: str            # Complaint description
source: str                 # Source (e.g., "Quality Control", "Customer Report")
date: str                   # Date in ISO format (e.g., "2026-03-16")
product: str                # Product information
```

#### Optional Fields
```
additional_context: str                 # Additional context information
pattern_data_json: str                 # JSON string of pattern analysis
similar_cases_data_json: str           # JSON string of similar cases analysis
similar_cases_json: str                # Legacy format (for backward compatibility)
metrics_file: UploadFile               # Custom metrics JSON file
data_file: UploadFile                  # Historical data file (Excel, PDF, etc.)
```

### Pattern Data JSON Structure

```json
{
  "complaint_id": "C-2026-002",
  "trend_score": 10,
  "trend_category": "Uncontrolled exponential trend",
  "confidence": 0.97,
  "matched_complaint_ids": [
    "NC-154", "NC-141", "NC-137", "NC-124", "NC-117",
    "NC-113", "NC-172", "NC-169", "NC-167", "NC-150", "NC-101"
  ],
  "identified_pattern": "Surface Defect in Orthopedic Implant across Site A, Site B, Site D and France, Germany, USA, UK, Japan",
  "explanation": "Eleven historical records share the Surface Defect failure type with the new complaint. These records span three sites (A, B, D) and five regions (France, Germany, USA, UK, Japan), indicating a widespread surface quality issue.",
  "error": null
}
```

### Similar Cases Data JSON Structure

```json
{
  "query": "device overheating, burn marks on casing",
  "similarityThreshold": 0.7,
  "similarCount": 2,
  "message": "Found 2 similar case(s) above the 70% similarity threshold.",
  "topMatches": [
    {
      "recordId": "NC 042-0042",
      "complaintId": "NC 042",
      "dateReceived": "2025-08-30T00:00:00",
      "source": "Supplier Audit",
      "regionCountry": null,
      "severity": "Low",
      "productFamily": "Stent",
      "site": "Site A",
      "descriptionOfIssue": "Overheating issue during device sterilization cycle",
      "status": "In Progress",
      "daysOpen": 77,
      "assignedTo": "Wei",
      "isNc": null,
      "ncId": null,
      "fieldAction": null,
      "euReportable": null,
      "fdaReportable": null,
      "capaNeeded": false,
      "capaId": null,
      "capaRationale": "CAPA not required for Low severity issue.",
      "repeated": false,
      "workflowStage": "NEW",
      "similarity": 0.7508
    }
  ]
}
```

### Legacy Similar Cases Format (Backward Compatibility)

```json
[
  {
    "case_id": "NC-042",
    "similarity_score": 0.75,
    "occurrence_factors": {
      "Historical Frequency of Events": "Low frequency, isolated incidents",
      "Trend Analysis / Pattern Recognition": "No clear trend identified",
      "Process Stability / Cp-Cpk Variability": "Process within control limits",
      "Effectiveness of Preventive Controls": "Controls functioning properly",
      "Effectiveness of Detection / Monitoring": "Detection rate >95%",
      "Systemic vs Isolated Issue": "Isolated to single batch",
      "Operator / Equipment Factors": "No operator issues identified",
      "CAPA / Past Corrective Actions Effectiveness": "Previous CAPAs effective",
      "Supplier / External Factors": "No supplier issues",
      "Audit / Compliance Findings": "No audit findings"
    }
  }
]
```

### Output Format

#### API Response Structure

```json
{
  "weighted_score": 7,
  "rating": "High",
  "breakdown": {
    "HF": 8,
    "TR": 9,
    "PS": 5,
    "PC": 6,
    "DM": 7,
    "SY": 8,
    "OE": 4,
    "CA": 6,
    "SU": 5,
    "AU": 3,
    "reasoning": "High occurrence score due to identified pattern across multiple sites with exponential trend and significant historical frequency."
  }
}
```

#### Parameter Breakdown Explanation

| Code | Parameter | Description |
|------|-----------|-------------|
| **HF** | Historical Frequency | How often this type of issue has occurred (1-10) |
| **TR** | Trend Analysis | Pattern recognition and trend direction (1-10) |
| **PS** | Process Stability | Statistical control and Cp/Cpk variability (1-10) |
| **PC** | Preventive Controls | Effectiveness of existing preventive measures (1-10) |
| **DM** | Detection/Monitoring | Effectiveness of detection systems (1-10) |
| **SY** | Systemic vs Isolated | Breadth of impact across batches/models (1-10) |
| **OE** | Operator/Equipment | Human factors and hardware stability (1-10) |
| **CA** | CAPA Effectiveness | Success rate of past corrective actions (1-10) |
| **SU** | Supplier Factors | External component quality and vendor risk (1-10) |
| **AU** | Audit Findings | Regulatory findings and compliance status (1-10) |

#### Rating Scale

| Score | Rating | Description |
|-------|--------|-------------|
| 1 | Remote | Extremely unlikely to occur |
| 2 | Very Low | Very unlikely to occur |
| 3 | Low | Unlikely to occur |
| 4 | Low-Moderate | Somewhat unlikely to occur |
| 5 | Moderate | May occur occasionally |
| 6 | Elevated Moderate | Likely to occur occasionally |
| 7 | High | Likely to occur |
| 8 | Very High | Very likely to occur |
| 9 | Critical | Almost certain to occur |
| 10 | Almost Certain | Will almost certainly occur |

---

## 🔧 Complete API Example

### Input (cURL)
```bash
curl -X POST "http://localhost:8000/occurrence/analyze" \
  -F "complaint_id=C-2026-002" \
  -F "description=Surface defect observed on orthopedic implant during quality inspection" \
  -F "source=Quality Control" \
  -F "date=2026-03-16" \
  -F "product=Orthopedic Implant - Hip Joint" \
  -F "additional_context=Device found during routine quality inspection" \
  -F 'pattern_data_json={"complaint_id":"C-2026-002","trend_score":10,"trend_category":"Uncontrolled exponential trend","confidence":0.97,"matched_complaint_ids":["NC-154","NC-141","NC-137"],"identified_pattern":"Surface Defect in Orthopedic Implant","explanation":"Pattern identified across multiple sites","error":null}' \
  -F 'similar_cases_data_json={"query":"surface defect","similarityThreshold":0.7,"similarCount":2,"message":"Found 2 similar cases","topMatches":[{"recordId":"NC-042","complaintId":"NC-042","severity":"Low","similarity":0.75,"capaNeeded":false}]}'
```

### Output
```json
{
  "weighted_score": 8,
  "rating": "Very High",
  "breakdown": {
    "HF": 9,
    "TR": 10,
    "PS": 6,
    "PC": 7,
    "DM": 6,
    "SY": 9,
    "OE": 5,
    "CA": 6,
    "SU": 4,
    "AU": 3,
    "reasoning": "Very high occurrence score driven by uncontrolled exponential trend (TR=10) and high historical frequency (HF=9) with systemic pattern across multiple sites (SY=9). Pattern analysis shows 97% confidence with multiple matched complaints indicating widespread surface quality issue."
  }
}
```

---

## 🛡️ Key Design Principles

### ⚡ Unified Evidence (Stability)
To eliminate LLM "wavering" between scores, history is pre-merged in Python. The LLM only sees the most relevant evidence, ensuring **100% deterministic output** for identical inputs.

### ⚓ Evidence-First Anchoring (Precision)
The agent must **Quote evidence** and **Match level descriptions** before providing a score. This anchors the AI reasoning to the provided text and prevents hallucinations.

### 🚨 Priority Override
Current complaint details are given **strict priority** over historical data. If a conflict occurs, the specific context of the current issue always wins.

---

## 📊 Scoring Parameters & Weights

### Primary Factors (52%)
*   **HF - Historical Frequency (18%)**: Focused on longitudinal recurrence rates.
*   **TR - Trend Analysis (12%)**: Detects pattern recognition and recurrence acceleration.
*   **PC - Preventive Controls (12%)**: Evaluates the technical efficacy of existing guards.
*   **SY - Systemic Risk (12%)**: Assesses the breadth of impact across batches or models.

### Secondary Factors (20%)
*   **PS - Process Stability (10%)**: Monitors statistical control and Cpk/Cp values.
*   **DM - Detection Reliability (10%)**: Visibility into failures before field/patient use.

### Supporting Factors (26%)
*   **OE - Operator/Equipment (8%)**: Human factors and hardware stability impact.
*   **CA - CAPA Effectiveness (8%)**: Success rate of past corrective actions.
*   **SU - Supplier Factors (5%)**: External component quality and vendor risk.
*   **AU - Audit Compliance (5%)**: Regulatory findings and internal audit status.

---

## 🪵 Traceability & Audit
Every analysis generates a deep audit log in `Agents/logs/occurrence.log`, capturing:
*   **API REQUEST Trace**: The exact request parameters and timestamp.
*   **LLM REASONING Trace**: The full Evidence-to-Score mapping chain.
*   **CALCULATION Trace**: The mathematical breakdown of the weighted result.
*   **FINAL STATE Trace**: The structured output for downstream systems.
