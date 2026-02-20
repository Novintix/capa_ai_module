# 🏥 CAPA Occurrence Agent

An advanced AI-driven risk assessment module designed to analyze medical device complaints and determine a deterministic **Occurrence Rating (1-10)** using LangGraph and AWS Bedrock.

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
