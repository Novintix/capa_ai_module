# Zero Evidence Agent

## Purpose

Activated when no validation evidence, observable signals, or historical data exists.
Determines the **Most Critical Functional Cause** from the provided FMEA cause list using
**first-principles reasoning and composite criticality scoring** — without generating new causes.

---

## Architecture

```
initialize
    │
validate_input          ← Guard: reject empty cause list
    │
llm_evaluate            ← Bedrock LLM: evaluates single-point failure, safety risk, and safety blocking per cause
    │
score_causes            ← Deterministic formula (no LLM):
    │                      0.35×severity + 0.20×SPF + 0.20×sys_dep + 0.15×safety + 0.10×blocking
select_cause            ← Picks the single highest-scored cause + calculates confidence
    │
finalize ──► END
```

## Criticality Scoring Formula

The agent evaluates causes using **5 key factors**:

### 1. Severity (35% weight)
- **What it measures**: Impact magnitude if the failure occurs
- **Source**: From FMEA document or LLM-assigned
- **Scale**: 1-10 (higher = more severe impact)

### 2. Single-Point Failure Potential (20% weight)
- **What it measures**: Can this cause ALONE produce the complete failure?
- **Evaluation**: LLM determines true/false
- **Scoring**: 
  - True (single-point failure) = 10 points
  - False (contributing factor) = 5 points

### 3. System Dependency (20% weight)
- **What it measures**: Is this component essential for system operation?
- **Evaluation**: Keyword matching between process step and question
- **Scoring**:
  - Direct dependency (keywords match) = 10 points
  - Indirect dependency = 5 points

### 4. Safety Impact (15% weight)
- **What it measures**: Level of safety risk to patients/users
- **Evaluation**: LLM analyzes potential_effects text
- **Scoring**:
  - High risk (dose errors, patient harm) = 10 points
  - Medium risk (confusion, misinterpretation) = 6 points
  - Low risk (minor issues) = 2 points

### 5. Safety Blocking Threshold (10% weight)
- **What it measures**: Does the system disable itself for safety reasons?
- **Evaluation**: LLM determines if safety interlocks exist
- **Scoring**:
  - Full blocking (system shuts down) = 10 points
  - Partial blocking (warnings/alerts) = 5 points
  - No blocking (continues operation) = 0 points

### Composite Score Formula

```
final_score = (0.35 × severity)
            + (0.20 × single_point_failure_score)
            + (0.20 × system_dependency_score)
            + (0.15 × safety_impact_score)
            + (0.10 × safety_blocking_score)
```

**Maximum possible score**: 10.0  
**Typical range**: 3.0 - 8.0

## Confidence Scoring

The agent calculates a **numerical confidence score (0.0-1.0)** based on:

1. **Final Score Magnitude**: Higher criticality scores indicate more confident selections
   - Normalized against maximum possible score (10.0)
   
2. **Score Separation**: Gap between top cause and second-best cause
   - Larger gaps (2+ points) = higher confidence
   - Small gaps = lower confidence
   
3. **LLM Evaluation Quality**: Presence of LLM reasoning
   - Has reasoning = 1.0x factor
   - No reasoning = 0.85x factor
   
4. **Severity Level**: Higher severity increases confidence
   - Severity ≥8: 1.0x factor
   - Severity 6-7: 0.95x factor
   - Severity 4-5: 0.85x factor
   - Severity <4: 0.75x factor

**Formula**: `confidence = score_confidence × separation_factor × llm_factor × severity_factor`

**Typical Ranges**:
- 0.80-1.0: High confidence (clear winner, high severity, good separation)
- 0.60-0.79: Medium confidence (moderate scores or close competition)
- 0.40-0.59: Low confidence (low scores or many similar causes)
- 0.0-0.39: Very low confidence (errors or poor data quality)

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/zero-evidence/` | Run analysis |
| GET | `/zero-evidence/health` | Health check |
