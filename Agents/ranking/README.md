# Ranking Agent

## Purpose
The Ranking Agent determines the most probable root cause among multiple candidate causes identified during investigation. The ranking is based on four evaluation dimensions using the Root Cause Priority Score (RCPS) methodology.

## Evaluation Dimensions

### 1. FMEA Risk Score (RPN) - 35% weight
- **Formula**: RPN = Severity × Occurrence × Detection
- Inherent risk of the failure mode based on FMEA standards
- Normalized to 0-1 scale for comparison

### 2. Evidence Strength - 30% weight
- **Observable (1.0)**: Direct logs, measurements, inspection records
- **Indirect (0.7)**: Operator observations, visual checks
- **Historical (0.5)**: Previous CAPA cases, maintenance records
- **None (0.3)**: No supporting evidence

### 3. Mechanism Fit - 20% weight
- **Strong (0.9)**: Cause directly explains the failure mode
- **Moderate (0.7)**: Cause partially explains the failure mode
- **Weak (0.4)**: Cause weakly relates to failure mode

### 4. Causal Proximity - 15% weight
- **Direct (1.0)**: Immediate trigger, directly causes failure
- **Contributor (0.7)**: Secondary factor, contributes to failure
- **Background (0.4)**: Distant cause, indirect relationship

## RCPS Formula

```
RCPS = 0.35 × RPN_score + 0.30 × Evidence + 0.20 × Mechanism + 0.15 × Proximity
```

## Input Format

```json
{
  "causes": [
    {
      "cause_id": "C001",
      "cause_text": "Excess ink, insufficient drying time",
      "process_step": "Syringe Marking",
      "failure_mode": "Smudged or blurred markings",
      "potential_effects": "Poor readability leading to dosing error",
      "severity": 7,
      "occurrence": 4,
      "detection": 5
    }
  ]
}
```

## Output Format

```json
{
  "ranked_causes": [
    {
      "rank": 1,
      "cause_id": "C002",
      "cause_text": "Ink adhesion failure",
      "rcps_score": 0.98,
      "rpn": 216,
      "rpn_score": 1.0,
      "evidence_strength": 1.0,
      "mechanism_fit": 0.9,
      "causal_proximity": 1.0,
      "risk_level": "High",
      "justification": "RPN: 216 (score: 1.00), Evidence: 1.0, Mechanism: 0.9, Proximity: 1.0"
    }
  ],
  "selected_root_cause": "C002",
  "total_causes": 4,
  "message": "Ranked 4 causes. Top root cause: C002 with RCPS 0.9800"
}
```

## Workflow

1. **Calculate RPN**: Compute Severity × Occurrence × Detection
2. **Normalize RPN**: Scale to 0-1 range (RPN / Max_RPN)
3. **Evaluate Evidence**: LLM scores evidence strength
4. **Evaluate Mechanism**: LLM scores mechanism fit
5. **Evaluate Proximity**: LLM scores causal proximity
6. **Calculate RCPS**: Apply weighted formula
7. **Rank & Format**: Sort by RCPS and generate output

## Risk Levels

- **High**: RCPS ≥ 0.75
- **Medium**: 0.50 ≤ RCPS < 0.75
- **Low**: RCPS < 0.50

## Regulatory Compliance

This methodology satisfies:
- ✅ ICH Q9 risk evaluation
- ✅ FDA investigation traceability
- ✅ ISO 13485 CAPA justification

Ranking is based on risk, evidence, and causal logic—not just probability.

## API Endpoints

### POST /ranking
Rank candidate root causes

### GET /ranking/health
Health check endpoint

## Usage Example

```python
from Agents.ranking.agent import RankingAgent

agent = RankingAgent()

causes = [
    {
        "cause_id": "C001",
        "cause_text": "Excess ink, insufficient drying time",
        "process_step": "Syringe Marking",
        "failure_mode": "Smudged or blurred markings",
        "potential_effects": "Poor readability leading to dosing error",
        "severity": 7,
        "occurrence": 4,
        "detection": 5
    }
]

result = agent.rank_causes(causes)
print(f"Top cause: {result.selected_root_cause}")
print(f"RCPS: {result.ranked_causes[0].rcps_score}")
```
