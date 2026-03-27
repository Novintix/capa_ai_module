# Fishbone v2 Orchestrator

## Overview

Production-grade single-depth fishbone analysis with 6M categorization and Redis state management.

## Key Features

✅ **Single Depth Analysis** - No iteration loops, one analysis per complaint  
✅ **6M Categorization** - Automatic classification into Man, Machine, Method, Material, Measurement, Environment  
✅ **Evidence-Based Validation** - Validates causes against evidence files  
✅ **Confidence-Based Routing** - Smart decision routing based on validation results  
✅ **Redis Session Management** - Production-grade state persistence  
✅ **Complete Error Handling** - Graceful fallbacks and error recovery  

## Flow

```
Complaint Description
    ↓
List Causes Agent (Generate causes from complaint)
    ↓
Categorization Agent (6M classification)
    ↓
Validation Agent (Evidence-based validation)
    ↓
Decision Router:
├─ 0 validated causes → Zero Evidence Agent (select & stop)
├─ 1 validated cause → Select it and stop
└─ >1 validated causes → Ranking Agent (select & stop)
    ↓
Root Cause with 6M Category
```

## 6M Categories

1. **Man (People)** - Human errors, training gaps, operator mistakes
2. **Machine (Equipment)** - Equipment failures, calibration issues
3. **Method (Process/SOP)** - Process design flaws, procedure gaps
4. **Material** - Raw material defects, supplier issues
5. **Measurement (Inspection)** - Detection failures, calibration problems
6. **Environment** - Temperature, humidity, cleanliness issues

## Installation

### 1. Start Redis (Docker)

```bash
cd orchestrator/fishbone_v2
docker-compose up -d
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## API Endpoints

### POST /fishbone-v2/

Run analysis with JSON input.

**Request:**
```json
{
  "complaint_id": "FISHBONE-2026-001",
  "complaint": "Tablet weight was incorrect during production batch #1234",
  "evidence": "Weight measurements show 5% deviation from specification",
  "fmea_document_path": "fmea.xlsx"
}
```

**Response:**
```json
{
  "complaint_id": "FISHBONE-2026-001",
  "root_cause": {
    "cause_id": "C002",
    "cause_text": "Compression force set incorrectly",
    "process_step": "Tablet Compression",
    "category": "Method",
    "category_confidence": 0.92,
    "severity": 8,
    "source": "FMEA",
    "reason": "Highest criticality score"
  },
  "confidence": "HIGH",
  "mode": "SINGLE_SHOT",
  "causes_found": 10,
  "causes": [...],
  "category_summary": {
    "Man": 2,
    "Machine": 3,
    "Method": 3,
    "Material": 1,
    "Measurement": 1
  },
  "validated_causes_count": 8,
  "high_confidence_causes_count": 5,
  "execution_time_seconds": 8.5
}
```

### POST /fishbone-v2/upload

Run analysis with file upload (multipart/form-data).

**Form Fields:**
- `complaint_id`: string (required)
- `complaint`: string (required)
- `evidence`: string (optional)
- `sop`: string (optional)
- `fmea_file`: file upload (optional)

### GET /fishbone-v2/health

Health check endpoint.

## Python Usage

```python
from orchestrator.fishbone_v2.agent import FishboneOrchestratorV2
from orchestrator.fishbone_v2.schemas import FishboneInput

# Initialize orchestrator
orchestrator = FishboneOrchestratorV2()

# Create input
input_data = FishboneInput(
    complaint_id="FISHBONE-2026-001",
    complaint="Tablet weight was incorrect during production",
    evidence="Weight measurements show 5% deviation",
    fmea_document_path="fmea.xlsx"
)

# Run analysis
result = orchestrator.analyze(input_data)

# Access results
print(f"Root Cause: {result['root_cause']['cause_text']}")
print(f"Category: {result['root_cause']['category']}")
print(f"Confidence: {result['confidence']}")
print(f"Category Summary: {result['category_summary']}")
```

## Testing

```bash
# Test with curl
curl -X POST "http://localhost:8000/fishbone-v2/" \
  -H "Content-Type: application/json" \
  -d '{
    "complaint_id": "TEST-001",
    "complaint": "Syringe marking was faded during production",
    "evidence": "Visual inspection shows 30% of batch affected"
  }'
```

## Redis Configuration

Default: `redis://localhost:6379`

Override with environment variable:
```bash
export REDIS_URL="redis://your-redis-host:6379"
```

## State Management

- **Session Key Format**: `fishbone_v2:session:{complaint_id}`
- **Session TTL**: 7 days (604800 seconds)
- **Automatic Cleanup**: Redis handles expiry
- **Session Reuse**: Completed sessions return cached results

## Architecture

### State Machine

```
INITIALIZING → LISTING_CAUSES → CATEGORIZING → VALIDATING → 
ROUTING_DECISION → [ZERO_EVIDENCE | RANKING] → ANALYSIS_COMPLETE
```

### Memory Types

1. **ExecutionMemory** - Complete iteration history
2. **ControlMemory** - Current state and decisions
3. **SessionMemory** - Redis-backed persistence

## Error Handling

- **Input Validation**: Prevents empty/invalid complaints
- **Agent Failures**: Graceful fallbacks to alternative methods
- **Redis Failures**: Clear error messages with connection details
- **FMEA Missing**: Automatic fallback to LLM generation

## Logging

Logs are written to: `orchestrator/logs/fishbone_v2.log`

Log levels:
- INFO: Normal operations, state transitions
- ERROR: Failures, exceptions

## Performance

- **Average Execution Time**: 8-12 seconds
- **With FMEA**: 8-10 seconds
- **Without FMEA**: 10-12 seconds (LLM generation)
- **Categorization Overhead**: ~2 seconds

## Differences from RCA v2

| Feature | RCA v2 | Fishbone v2 |
|---------|--------|-------------|
| Depth | Multiple iterations | Single depth only |
| Question Generation | Yes (Why questions) | No (direct from complaint) |
| Categorization | Optional at depth 1 | Always (6M categories) |
| Loop Control | Yes | No |
| Use Case | Deep root cause analysis | Quick fishbone diagrams |

## Production Checklist

- [ ] Redis running and accessible
- [ ] Environment variables configured
- [ ] FMEA documents accessible
- [ ] Evidence files accessible
- [ ] Logging directory writable
- [ ] API endpoints tested
- [ ] Error handling verified

## Troubleshooting

**Redis Connection Failed:**
```bash
# Check Redis is running
docker ps | grep redis

# Test connection
redis-cli ping
```

**No Causes Generated:**
- Check FMEA file path is correct
- Verify FMEA file format
- Check LLM fallback is working

**Categorization Failed:**
- Check categorize agent is available
- Verify LLM connection
- Check logs for detailed error

## Support

For issues or questions, check:
1. Logs: `orchestrator/logs/fishbone_v2.log`
2. Redis: `redis-cli monitor`
3. Health endpoint: `GET /fishbone-v2/health`
