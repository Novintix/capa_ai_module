# Fishbone Orchestrator

## Overview

The Fishbone Orchestrator is an enhanced version of RCA v2 that adds **6M Categorization** at depth 1 for Fishbone (Ishikawa) diagram analysis.

## Key Difference from RCA v2

**RCA v2**: Question → Cause Generation → Validation → Ranking/Selection

**Fishbone**: Question → Cause Generation → **Categorization (Depth 1 Only)** → Validation → Ranking/Selection

## 6M Categories

At depth 1, all causes are automatically categorized into:

1. **Man (People)** - Human errors, training gaps, operator mistakes
2. **Machine (Equipment)** - Equipment failures, calibration issues, automation problems
3. **Method (Process/SOP)** - Process design flaws, inadequate procedures, setup errors
4. **Material** - Raw material defects, wrong grades, supplier issues
5. **Measurement (Inspection)** - Detection failures, inspection gaps, calibration problems
6. **Environment** - Temperature, humidity, cleanliness, external factors

## Output Format

### Depth 1 Iteration (with Categorization)

```json
{
  "depth": 1,
  "question": "Why was the tablet weight incorrect?",
  "causes_found": 10,
  "causes": [
    {
      "cause_id": "C001",
      "cause_text": "Compression force set incorrectly",
      "category": "Method",
      "category_confidence": 0.92,
      "category_reasoning": "Process parameter setting issue",
      "secondary_categories": ["Man"],
      "source": "FMEA"
    },
    {
      "cause_id": "C002",
      "cause_text": "Load cell sensor drift",
      "category": "Machine",
      "category_confidence": 0.88,
      "category_reasoning": "Equipment calibration issue",
      "secondary_categories": ["Measurement"],
      "source": "FMEA"
    }
  ]
}
```

**Note:** Each cause at depth 1 has `category`, `category_confidence`, `category_reasoning`, and `secondary_categories` fields.

### Depth 2+ Iterations (No Categorization)

```json
{
  "depth": 2,
  "question": "Why was the compression force set incorrectly?",
  "causes_found": 5,
  "causes": [
    {
      "cause_id": "C001",
      "cause_text": "Operator training insufficient",
      "source": "FMEA"
    }
  ]
}
```

**Note:** Causes at depth 2+ do NOT have category fields.

## Usage

### Python

```python
from Agents.fishbone_orchestrator.agent_integrated import FishboneOrchestratorIntegrated
from Agents.fishbone_orchestrator.schemas import WhyAnalysisInput

orchestrator = FishboneOrchestratorIntegrated()

input_data = WhyAnalysisInput(
    complaint_id="FISHBONE-001",
    complaint="Tablet weight incorrect",
    evidence="Weight measurements show deviations",
    fmea_document_path="fmea.xlsx",
    max_depth=3
)

result = orchestrator.analyze(input_data)

# Access depth 1 causes with categories
depth_1 = result["why_iterations"][0]
for cause in depth_1["causes"]:
    print(f"{cause['cause_text']}: {cause.get('category', 'N/A')}")
```

### API (if router is set up)

```bash
POST /fishbone/analyze
Content-Type: application/json

{
  "complaint_id": "FISHBONE-001",
  "complaint": "Tablet weight incorrect",
  "evidence": "Weight measurements show deviations",
  "fmea_document_path": "fmea.xlsx",
  "max_depth": 3
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  FISHBONE ORCHESTRATOR                                      │
│  (Same as RCA v2 + Categorization at Depth 1)              │
└─────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────────────────────────────┐
        │                                               │
        ▼                                               ▼
┌─────────────────────────────────────┐   ┌─────────────────────────────┐
│      DEPTH 1 FLOW                   │   │    DEPTH 2+ FLOW            │
│  (With Categorization)              │   │  (No Categorization)        │
└─────────────────────────────────────┘   └─────────────────────────────┘
        │                                               │
        ▼                                               ▼
  Question Agent                                  Question Agent
        │                                               │
        ▼                                               ▼
  Cause Generation                                Cause Generation
        │                                               │
        ▼                                               │
  **CATEGORIZATION AGENT** ◄─── NEW!                   │
        │                                               │
        ▼                                               ▼
  Validation Agent                                Validation Agent
        │                                               │
        ▼                                               ▼
  Ranking/Selection                               Ranking/Selection
```

## When to Use

**Use Fishbone Orchestrator when:**
- You need Fishbone (Ishikawa) diagram categorization
- You want to visualize causes by 6M categories
- You need structured root cause analysis with categorization
- You're doing manufacturing/quality analysis

**Use RCA v2 when:**
- You don't need categorization
- You want faster analysis (no categorization overhead)
- You're doing general root cause analysis

## Performance

- **Depth 1**: +5-10 seconds (categorization overhead)
- **Depth 2+**: Same as RCA v2 (no categorization)

## Dependencies

- All RCA v2 dependencies
- Categorization Agent (Agents/categorize)

## Testing

```bash
python test_fishbone.py
```

## Notes

- Categorization only runs at depth 1
- Category fields are only present in depth 1 causes
- `category_summary` is only present in depth 1 iteration
- Depth 2+ iterations work exactly like RCA v2
