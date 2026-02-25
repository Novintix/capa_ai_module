# CAPA Action Plan Agent

**Regulated Manufacturing CAPA Action Planning** — FDA / ISO Compliant

Generates audit-ready Corrective & Preventive Action (CAPA) plans from root cause analysis.

## Overview

The CAPA Action Plan Agent transforms investigation data and root cause analysis into a structured, 9-column action plan that meets FDA 21 CFR 211 and ISO standards.

**Input**: Investigation summary, containment actions, 5-Why analysis, root causes
**Output**: Audit-ready action plan with departments, timelines, resources, verification

## Architecture

```
┌─────────────────────────────────────┐
│  POST /action_plan (CapaInput)     │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  generate_actions_node              │
│  (LLM enforces CAPA rules)          │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  validate_actions_node              │
│  (Verify compliance)                │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  CapaActionPlanResponse (9 columns) │
└─────────────────────────────────────┘
```

## Input Schema (CapaInput)

```json
{
  "investigation_summary": "...",
  "containment_actions": "...",
  "five_why_analysis": "...",
  "primary_root_cause": "...",
  "contributing_root_causes": ["...", "..."],
  "systemic_root_causes": ["..."],
  "evidence_collected": "...",
  "root_cause_verification_status": "Verified|Pending|Not Required",
  "severity_level": "Critical|Major|Minor",
  "timeline_constraint": "30 days|90 days",
  "available_resources": "description"
}
```

## Output Schema (9 Columns)

```json
{
  "action_items": [
    {
      "action_type": "Corrective|Preventive|Systemic",
      "action_description": "Specific, measurable description",
      "assigned_to": "Department (e.g., QA, Manufacturing)",
      "planned_due_date": "YYYY-MM-DD",
      "resources_required": "Description of resources",
      "verification_plan": "Measurable validation method",
      "training_requirements": "Yes - TR-001|No",
      "document_updates_required": "SOP-001, WI-002|N/A",
      "change_control_reference": "CC-001|EC-001|SC-001|N/A"
    }
  ],
  "total_actions": 5,
  "primary_actions": 2,
  "preventive_systemic_actions": 3,
  "confidence_score": 0.92,
  "notes": "Audit-ready plan"
}
```

## CAPA Rules Enforced

### Rule 1: Action Coverage
- **Every root cause** generates ≥1 Corrective + ≥1 Preventive/Systemic action

### Rule 2: Action Descriptions
- Specific and measurable (avoid generic wording)
- State exactly what will change
- Include success criteria

### Rule 3: Assignment
- **Department-level only** (Manufacturing, QA, R&D, etc.)
- Never use individual names

### Rule 4: Due Dates
- Format: `YYYY-MM-DD`
- Critical issues: 30-60 days
- Preventive: 60-120 days

### Rule 5: Verification
- Must include measurable validation
- Examples: Validation Report Review, Audit Closure, DV Report, Sampling Data, Capability Study

### Rule 6: Training
- SOP/WI changes → `Yes - TR-XXX`
- No procedural change → `No`

### Rule 7: Document Updates
- List document IDs: `SOP-001`, `WI-002`, `Spec-005`
- No update → `N/A`

### Rule 8: Change Control
- Process parameter update → `CC-###` (Process Change Control)
- SOP/WI update → `CC-###` (QMS Change Control)
- Design change → `EC-###` (Engineering Change)
- Supplier qualification → `SC-###` (Supplier Change)
- No structural change → `N/A`

## API Usage

### POST /action_plan

```bash
curl -X POST http://localhost:8000/action_plan \
  -H "Content-Type: application/json" \
  -d '{
    "capa_input": {
      "investigation_summary": "Contamination detected in batch X-001",
      "containment_actions": "Batch quarantined, line cleaned",
      "five_why_analysis": "Why 1: Improper cleaning...",
      "primary_root_cause": "Equipment maintenance schedule gap",
      "evidence_collected": "Maintenance logs show 3-month gap",
      "root_cause_verification_status": "Verified",
      "severity_level": "Critical",
      "timeline_constraint": "30 days"
    }
  }'
```

### Response

```json
{
  "action_items": [
    {
      "action_type": "Corrective",
      "action_description": "Implement daily equipment inspection checklist with documented verification",
      "assigned_to": "Manufacturing",
      "planned_due_date": "2026-03-15",
      "resources_required": "Inspection checklist template, calibrated measurement tools",
      "verification_plan": "Audit Review of completed inspection logs for 30 days",
      "training_requirements": "Yes - TR-001",
      "document_updates_required": "WI-005 Equipment Maintenance, SOP-012 Cleaning",
      "change_control_reference": "CC-001"
    },
    {
      "action_type": "Preventive",
      "action_description": "Establish automated maintenance scheduling system with alert notifications",
      "assigned_to": "Maintenance",
      "planned_due_date": "2026-05-15",
      "resources_required": "CMMS software license, training, IT support",
      "verification_plan": "System capability review and scheduled alert test",
      "training_requirements": "Yes - TR-002",
      "document_updates_required": "SOP-015 Preventive Maintenance Program",
      "change_control_reference": "CC-002"
    }
  ],
  "total_actions": 2,
  "primary_actions": 1,
  "preventive_systemic_actions": 1,
  "confidence_score": 0.94,
  "notes": "Plan meets FDA 21 CFR 211 requirements"
}
```

## Files

| File | Purpose |
|------|---------|
| `model.py` | Pydantic schemas (CapaInput, CapaActionItem, Response) |
| `state.py` | LangGraph ActionPlanState |
| `prompts.py` | LLM prompt with all CAPA rules |
| `nodes.py` | Two nodes: generate_actions, validate_actions |
| `graph.py` | LangGraph workflow |
| `router.py` | FastAPI `/action_plan` endpoint |
| `logger.py` | Central logging to `Agents/logs/action_plan.log` |
| `example_usage.py` | Working examples with real CAPA scenarios |
| `test_action_plan.py` | Unit and integration tests |

## Python Usage

```python
from Agents.action_plan.graph import build_graph
from Agents.action_plan.model import CapaInput

graph = build_graph()

capa_input = CapaInput(
    investigation_summary="...",
    containment_actions="...",
    five_why_analysis="...",
    primary_root_cause="...",
    evidence_collected="...",
    root_cause_verification_status="Verified"
)

result = graph.invoke({
    "capa_input": capa_input.dict()
})

for action in result["action_items"]:
    print(f"{action['action_type']:12} | {action['assigned_to']:15} | {action['planned_due_date']}")
```

## Environment

Requires `.env` with AWS Bedrock:
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

## Compliance & Audit

- ✅ FDA 21 CFR 211 compliant
- ✅ ISO 13485 compliant (Medical Device Quality)
- ✅ Validates all 9 required columns
- ✅ Enforces department assignments (no individuals)
- ✅ Ensures measurable verification plans
- ✅ Audit log trails in `Agents/logs/action_plan.log`
- ✅ Confidence scores indicate audit readiness

## Logging

All activity logged to `Agents/logs/action_plan.log`:
- Node entry/exit
- Action item generation
- Validation checks
- Errors and warnings

Run integration tests to validate full compliance.
