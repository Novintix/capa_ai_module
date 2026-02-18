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
Input: Complaint + Policy Rules
  ↓
1. Normalize (standardize severity, country, issue_type)
  ↓
2. Evaluate Rules (match complaint fields to rule conditions)
  ↓
3. Select Rule (highest priority if multiple match)
  ↓
4. Calculate Timeline (working/calendar days from awareness date)
  ↓
5. Extract Decision (reportability, authority, CAPA)
  ↓
6. Generate Justification (LLM explains why)
  ↓
Output: Regulatory Decision
```

## Key Features

- **Fully Dynamic**: Accepts any complaint fields (risk_score, batch_number, etc.)
- **Flexible Rules**: Policy conditions can check any field
- **Semantic Matching**: Uses embeddings for description keywords
- **Multiple Authorities**: Collects all authorities from matched rules
- **No Hardcoding**: All decisions from policy, not hardcoded logic

## Input

**Required**: complaint_id, description, date_of_awareness

**Optional**: severity, issue_type, distributed_to_market, risk_score, etc.

## Output

- Reportable (yes/no)
- Authority (FDA, EU, etc.)
- Timeline & due date
- CAPA requirement
- Justification with confidence

## Configuration

- Model: AWS Bedrock (config/aws_bedrock_config.py)
- Embeddings: sentence-transformers (open source)
- Logs: logs/regulatory_agent_YYYYMMDD.log
