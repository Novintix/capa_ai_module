# Why Analysis V3 Orchestrator

## Overview

Why Analysis V3 is a simplified root cause analysis orchestrator with human-in-the-loop validation. Following the architecture patterns from `risk_analysis_orchestrator_service`, it provides clean separation of concerns, proper payload building, and complete observability.

## Architecture

### Flow

```
START
  ↓
initialize (validate input, setup state)
  ↓
payload_builder (build all agent payloads)
  ↓
question_agent (generate Why question)
  ↓
cause_generation_agent (generate potential causes)
  ↓
validation_agent (validate causes against evidence)
  ├─ 0 validated causes → zero_evidence_agent → finalize → END (ai_flagged)
  ├─ All causes < 90% confidence → zero_evidence_agent → finalize → END (ai_flagged)
  └─ 1+ causes with ≥90% confidence → human_review (PAUSED)
                              ↓
                         [Human selects cause + decision]
                              ├─ decision="root_cause" → finalize → END (completed)
                              └─ decision="continue" → payload_builder (next iteration)
                                                          ↓
                                                     [Loop back for 5-Why analysis]
```

### Confidence Threshold Logic

The orchestrator uses a **dual-criteria filter** to determine the flow:

**Qualified Causes Must Have BOTH:**
1. **Confidence ≥90%**: Validation confidence ≥ 0.90
2. **Matched Evidence**: evidence_match_status = "matched"

**Routing Logic:**
- **1+ qualified causes** → Human review (expert decides)
  - → **Only qualified causes shown to user**
  - → Unmatched or low confidence causes filtered out
  - → Enables iterative deepening (5-Why)

- **0 qualified causes** → Zero evidence mode (AI selects by criticality)
  - → Ends analysis automatically
  - → Flags for manual investigation

**Example Filtering:**
```
Validation returns 5 causes:
- C001: 95% confidence, matched     → Shown ✓
- C002: 92% confidence, matched     → Shown ✓
- C003: 95% confidence, not_matched → Hidden ✗
- C004: 78% confidence, matched     → Hidden ✗
- C005: 91% confidence, matched     → Shown ✓

Result: User sees only 3 qualified causes (C001, C002, C005)
```

### Iterative Deepening (5-Why Analysis)

The orchestrator supports true 5-Why analysis through iterative deepening:

1. **First Iteration**: Analyze initial complaint → Get validated causes → Check confidence threshold
2. **Confidence Check**:
   - If any cause ≥90% confidence → Human reviews and decides
   - If all causes <90% confidence → Zero evidence mode (AI selects)
3. **Human Decision** (when confidence ≥90%):
   - `"root_cause"`: Selected cause is the final root cause → End analysis
   - `"continue"`: Dig deeper → Ask "Why?" about the selected cause → Next iteration
4. **Subsequent Iterations**: Repeat until human identifies root cause or confidence drops below 90%

Each iteration:
- Generates a new Why question based on the previously selected cause
- Finds new causes related to that question
- Validates those causes
- Checks confidence threshold
- Either presents to human (≥90%) or auto-selects (< 90%)
- Builds a complete why_chain showing the analysis path

### Confidence Threshold: 90%

The 90% threshold ensures:
- **High confidence causes** → Human expertise applied for critical decisions
- **Low confidence causes** → AI handles automatically to avoid wasting expert time
- **Quality control** → Only well-validated causes require human review
- **Efficiency** → Automatic handling of uncertain cases

### Key Principles

Following `risk_analysis_orchestrator_service` patterns:

1. **Payload Building**: Separate `payloads.py` for all agent payload construction
2. **Deep Serialization**: `deep_serialize()` applied to all agent results
3. **Tracking IDs**: `complaint_id` and `session_id` for complete traceability
4. **Context Passing**: All evidence fields properly passed to agents
5. **Redis Checkpointing**: Full state persistence with pause/resume
6. **Node-Based Routing**: All routing logic in routing functions, not in nodes
7. **Observability**: Complete `node_log` and error tracking
8. **Confidence Threshold**: 90% threshold determines human review vs auto-selection
9. **No Prompts File**: Unlike risk_analysis, this orchestrator doesn't need a prompts.py file

## Components

### Files

- `orchestrator.py` - Main orchestrator with node functions and routing
- `payloads.py` - Per-agent payload builders
- `state.py` - State definitions with proper typing
- `schemas.py` - Pydantic input/output models
- `agent.py` - Wrapper class for orchestrator
- `router.py` - FastAPI endpoints
- `logger.py` - Logging utilities

### Agents Used

1. **Question Agent** - Generates Why questions
2. **Cause Generation Agent** - Generates potential causes (with optional FMEA)
3. **Validation Agent** - Validates causes against evidence
4. **Zero Evidence Agent** - Selects cause by criticality (when validation returns 0)

### Removed from V2

- Loop Control Agent
- Ranking Agent

## API Endpoints

### 1. Start Analysis

```http
POST /why-analysis-v3/
Content-Type: application/json

{
  "complaint_id": "CAPA-2024-001",
  "complaint": "Incorrect dosage values in prescription summary",
  "evidence": "Investigation logs show database timeout errors...",
  "sop": "Standard procedure requires validation...",
  "fmea_document_path": null,
  "logs": "2024-01-15 14:23:45 ERROR: Database connection timeout",
  "reports": "Incident Report IR-2024-015...",
  "process_data": "Peak load: 500 concurrent users..."
}
```

**Response (awaiting human review - high confidence):**
```json
{
  "complaint_id": "CAPA-2024-001",
  "session_id": "uuid-generated",
  "status": "awaiting_human_review",
  "awaiting_human_review": true,
  "human_review_message": "Please review and select one of the 3 validated cause(s).",
  "validated_causes": [
    {
      "cause_id": "C-001",
      "cause_text": "Database connection pool exhaustion...",
      "validation_confidence": 0.95,
      "evidence_match_status": "matched"
    }
  ]
}
```

**Response (zero evidence - low confidence):**
```json
{
  "complaint_id": "CAPA-2024-001",
  "session_id": "uuid-generated",
  "status": "ai_flagged",
  "ai_flagged": true,
  "stopping_reason": "low_confidence_zero_evidence",
  "root_cause": {
    "cause_id": "C-001",
    "cause_text": "...",
    "selection_path": "zero_evidence_mode",
    "confidence_score": 0.75
  },
  "validation_summary": {
    "total_validated_causes": 3,
    "overall_confidence": 0.75,
    "max_confidence": 0.85
  }
}
```

**Response (zero evidence - no causes):**
```json
{
  "complaint_id": "CAPA-2024-001",
  "session_id": "uuid-generated",
  "status": "ai_flagged",
  "ai_flagged": true,
  "stopping_reason": "no_validated_cause_zero_evidence",
  "root_cause": {
    "cause_id": "C-001",
    "cause_text": "...",
    "selection_path": "zero_evidence_mode"
  }
}
```

### 2. Submit Human Review

```http
POST /why-analysis-v3/human-review
Content-Type: application/json

{
  "session_id": "uuid-from-previous-response",
  "selected_cause_id": "C-001",
  "decision": "root_cause"
}
```

**Decision Options:**
- `"root_cause"` (default): Treat selected cause as final root cause → End analysis
- `"continue"`: Dig deeper → Ask Why again with this cause → Next iteration (5-Why)

**Response (decision="root_cause"):**
```json
{
  "complaint_id": "CAPA-2024-001",
  "session_id": "uuid",
  "status": "completed",
  "stopping_reason": "human_approved_root_cause",
  "root_cause": {
    "cause_id": "C-001",
    "cause_text": "...",
    "selection_path": "human_review",
    "confidence_score": 0.85
  },
  "why_chain": [
    {
      "loop": 1,
      "question": "Why did...",
      "selected_cause": "...",
      "decision": "root_cause",
      "human_approved": true
    }
  ]
}
```

**Response (decision="continue" - Next Iteration):**
```json
{
  "complaint_id": "CAPA-2024-001",
  "session_id": "uuid",
  "status": "awaiting_human_review",
  "analysis_depth": 2,
  "awaiting_human_review": true,
  "human_review_message": "Please review and select one of the 5 validated cause(s).",
  "validated_causes": [
    {
      "cause_id": "C-101",
      "cause_text": "Deeper cause related to previous selection...",
      "validation_confidence": 0.78
    }
  ],
  "why_chain": [
    {
      "loop": 1,
      "question": "Why did...",
      "selected_cause": "...",
      "decision": "continue",
      "human_approved": true
    }
  ]
}
```

### 3. Check Status

```http
GET /why-analysis-v3/status/{session_id}
```

### 4. Get Full State

```http
GET /why-analysis-v3/state/{session_id}
```

### 5. Health Check

```http
GET /why-analysis-v3/health
```

## Testing in Postman

### Quick Test with FMEA

The project includes `fmea_depth_test_large.xlsx` with tablet manufacturing FMEA data. Use this for realistic testing.

### Test 1: Tablet Weight Issue (With FMEA)

**Request:**
```json
POST http://localhost:8000/why-analysis-v3/

{
  "complaint_id": "CAPA-2024-001",
  "complaint": "Multiple batches of tablets showing incorrect weight. Batch #2024-TBL-045 had tablets weighing 520mg instead of specified 500mg ±5%. Quality control detected 15 out of 100 tablets outside specification during routine sampling.",
  "evidence": "Batch records show compression force was set at 12kN instead of specified 10kN. Load cell calibration certificate dated 6 months ago. Operator training records current. Weight monitoring system flagged deviation at 14:30 on production line 2.",
  "sop": "SOP-PROD-001: Tablet Compression requires compression force verification before each batch. Weight checks every 30 minutes. Calibration quarterly. Acceptable range: 500mg ±5% (475-525mg).",
  "fmea_document_path": "fmea_depth_test_large.xlsx",
  "logs": "2024-01-15 14:30:22 WARN: Weight deviation detected\n2024-01-15 14:30:45 ERROR: 15 tablets out of spec\n2024-01-15 14:31:10 INFO: Production line 2 paused",
  "reports": "Quality Control Report QC-2024-045: Tablet weight out of specification. Impact: 1500 tablets affected. Severity: Medium. Batch quarantined pending investigation.",
  "process_data": "Compression force: 12kN (spec: 10kN). Tablet hardness: 8kP (spec: 6-10kP). Production rate: 5000 tablets/hour.",
  "historical_capa": "Previous CAPA-2023-156 addressed similar weight issue. Root cause: Operator setup error. Corrective action: Enhanced training program implemented."
}
```

**Expected Response:**
- Status: `"awaiting_human_review"`
- Validated causes matching FMEA entries:
  - Compression force set incorrectly
  - Load cell sensor drift
  - Powder feed inconsistency
- Strong evidence match with high confidence

**Then submit:**
```json
POST http://localhost:8000/why-analysis-v3/human-review

{
  "session_id": "<session_id_from_above>",
  "selected_cause_id": "C-001"
}
```

### Test 2: Zero Evidence Flow

**Request:**
```json
POST http://localhost:8000/why-analysis-v3/

{
  "complaint_id": "CAPA-2024-002",
  "complaint": "System error occurred",
  "evidence": "",
  "sop": ""
}
```

**Expected:** `status: "ai_flagged"` with `root_cause` from zero_evidence_agent

### Automated Testing

Run the included test script:

```bash
python orchestrator/why_analysis_v3/run_tests.py
```

This will:
1. Check service health
2. Load test cases from `test_complaints.json`
3. Run selected tests interactively
4. Prompt for human cause selection
5. Display results and summary

Test cases included:
1. Tablet Weight Issue (With FMEA)
2. Tablet Hardness Issue (With FMEA)
3. Granulation Issue (With FMEA)
4. Calibration Failure (With FMEA)
5. Zero Evidence Test (No FMEA)
6. Complex Multi-Factor Issue (With FMEA)

## Payload Building

All agent payloads are built in `payloads.py`:

```python
def build_all_payloads(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "question": question_payload(state),
        "cause_generation": cause_generation_payload(state),
        "validation": validation_payload(state),
        "zero_evidence": zero_evidence_payload(state),
    }
```

Each payload function:
- Accepts full state
- Returns dict matching agent's expected schema
- Handles all context and evidence fields
- Includes tracking IDs (complaint_id, session_id)

## State Management

### Input Fields
- `complaint_id`: Unique identifier (required)
- `complaint`: Issue description (required)
- `evidence`: Investigation evidence
- `sop`: Standard Operating Procedures
- `fmea_document_path`: Optional FMEA document
- Optional: `logs`, `reports`, `process_data`, `historical_capa`, `policies`, `investigation_records`, `supporting_system_information`

### Runtime Fields
- `agent_payloads`: Built by payload_builder_node
- `current_loop_count`: Current iteration
- `current_why_question`: Generated question
- `current_causes`: Generated causes
- `validated_causes_enriched`: Validated causes with evidence match

### Human Review Fields
- `awaiting_human_review`: Boolean flag
- `human_review_message`: Message for reviewer
- `human_selected_cause_id`: ID of selected cause
- `current_selected_cause`: Full selected cause object

### Output Fields
- `status`: "running" | "awaiting_human_review" | "completed" | "ai_flagged" | "error"
- `root_cause`: Final selected cause
- `why_chain`: History of questions and answers
- `ai_flagged`: Boolean indicating zero evidence mode
- `stopping_reason`: Reason for workflow termination

## Redis Session Management

- **Automatic Checkpointing**: State saved after each node
- **Session ID**: Unique identifier for each analysis
- **Pause/Resume**: Workflow pauses at human_review node
- **TTL**: 7 days (configurable in Redis)

## Observability

### Logging
- File: `Agents/logs/why_analysis_v3.log`
- Includes: Node entry/exit, errors, agent results

### Node Log
Each node execution logged with:
- `node`: Node name
- `status`: "success" | "error" | "awaiting_input"
- `timestamp`: ISO-8601 timestamp
- Additional context (e.g., causes_count, validated_count)

### Tracking
- `complaint_id`: Tracks complaint across all agents
- `session_id`: Tracks workflow session in Redis
- `loop`: Current iteration number

## Error Handling

- **Retries**: Each agent call retried up to `MAX_NODE_RETRIES` (2) times
- **Fallback Causes**: Deterministic fallback if cause generation returns empty
- **Error State**: All errors captured in `errors` array with node, message, timestamp
- **Graceful Degradation**: FMEA failure falls back to LLM-only mode

## Configuration

### Redis URL
Set in `config/redis_config.py`:
```python
REDIS_URL = "redis://localhost:6379"
```

### Agent Retries
```python
MAX_NODE_RETRIES = 2  # Attempts per node before error
```

## Differences from V2

| Feature | V2 | V3 |
|---------|----|----|
| Loop Control | ✅ Automatic | ❌ Removed |
| Ranking | ✅ Multi-cause | ❌ Removed |
| Human Review | ❌ None | ✅ Mandatory |
| Iterations | Multiple (5+) | Single |
| Pause/Resume | ❌ No | ✅ Yes |
| Payload Building | Inline | ✅ Separate file |
| Tracking IDs | Partial | ✅ Complete |

## Integration

Add to main FastAPI app:

```python
from orchestrator.why_analysis_v3.router import router as why_v3_router

app.include_router(why_v3_router)
```

## Performance

Expected execution times (approximate):
- Initialize + Payload Builder: < 200ms
- Question Agent: 2-5 seconds
- Cause Generation Agent: 3-8 seconds
- Validation Agent: 5-10 seconds
- Zero Evidence Agent: 3-6 seconds
- Human Review: Instant (state update only)

Total (excluding human wait): 10-25 seconds

## Logs

Check logs for detailed execution trace:
```bash
tail -f Agents/logs/why_analysis_v3.log
```

## Next Steps

1. Integrate with main FastAPI app
2. Add authentication/authorization
3. Implement notification system for human review
4. Add metrics and monitoring
5. Deploy to production environment
