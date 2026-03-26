# RCA v2 Orchestrator - State Machine Implementation

## Overview

RCA v2 is an improved version of the Why Analysis Orchestrator that implements proper state machine principles with controlled memory management. This addresses the key issues identified in the original implementation.

## Key Improvements

### ✅ **Central JSON State Object**
- `RCAStateMachine` class manages all state
- Defined states: `INITIALIZING`, `QUESTIONING`, `CAUSE_FINDING`, `CAUSE_RANKING`, `ITERATION_COMPLETE`, `ANALYSIS_COMPLETE`, `ERROR`
- State transition validation
- Controlled state mutations

### ✅ **Controlled LLM Context**
- LLM receives curated context, not full conversation history
- `LLMContextManager` controls what context LLM gets
- For questions: Only last iteration + original complaint
- For ranking: Limited to top 10 causes
- No raw memory dumps to LLM

### ✅ **Orchestrator-Only Memory Updates**
- LLM never updates memory directly
- All memory changes controlled by orchestrator
- Clear separation of concerns
- Memory updates happen after LLM calls, not during

### ✅ **Separate Memory Types**
- **ExecutionMemory**: Complete detailed history for orchestrator
- **ControlMemory**: Current state, decisions, transitions
- **LLM Context**: Curated, relevant context only
- Each memory type has specific purpose and access patterns

### ✅ **Proper State Machine**
- Defined state transitions with validation
- State transition logging
- Error state handling
- Clear stopping conditions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RCA v2 Orchestrator                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ ExecutionMemory │  │ ControlMemory   │  │LLMContextManager│  │
│  │                 │  │                 │  │                 │  │
│  │ • Iterations    │  │ • Current State │  │ • Question Ctx  │  │
│  │ • Causes        │  │ • Depth         │  │ • Ranking Ctx   │  │
│  │ • Transitions   │  │ • Stop Reason   │  │ • Controlled    │  │
│  │ • Full History  │  │ • Confidence    │  │   Context       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    RCAStateMachine                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ States: INIT → QUESTIONING → CAUSE_FINDING → CAUSE_RANKING │ │
│  │         → ITERATION_COMPLETE → ANALYSIS_COMPLETE           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## State Flow

```
INITIALIZING
    ↓
QUESTIONING (Generate Why question with controlled context)
    ↓
CAUSE_FINDING (Call Cause Generation Agent)
    ↓
CAUSE_RANKING (Call Zero Evidence Agent with limited causes)
    ↓
ITERATION_COMPLETE (Update memories, check stopping conditions)
    ↓
QUESTIONING (Next iteration) OR ANALYSIS_COMPLETE (Stop)
```

## Memory Management

### ExecutionMemory (Orchestrator Only)
```python
@dataclass
class ExecutionMemory:
    iterations: List[IterationMemory]
    total_causes_analyzed: int
    start_time: float
    state_transitions: List[Dict[str, Any]]
```

### ControlMemory (Orchestrator Only)
```python
@dataclass
class ControlMemory:
    current_state: RCAState
    current_depth: int
    max_depth: int
    mode: str
    stop_reason: Optional[StopReason]
    final_root_cause: Optional[Dict[str, Any]]
```

### LLM Context (Controlled)
```python
# Question Context (NOT full history)
context = f"""ORIGINAL COMPLAINT: {complaint}

PREVIOUS ANALYSIS:
Question: {last_iteration.question}
Selected Cause: {last_iteration.selected_cause}

Generate the next "Why?" question to dig deeper."""

# Ranking Context (Limited causes)
context = {
    "question": question,
    "causes": causes[:10],  # Top 10 only
    "total_causes": len(causes)
}
```

## API Endpoints

### JSON Input
```
POST /rca-v2/
Content-Type: application/json

{
  "complaint_id": "CAPA-2026-001",
  "complaint": "Syringe marking was faded during production",
  "fmea_document_path": "fmea.xlsx"
}
```

### Form Data with File Upload
```
POST /rca-v2/upload
Content-Type: multipart/form-data

complaint_id: CAPA-2026-001
complaint: Syringe marking was faded during production
fmea_file: [Excel file upload]
```

### Health Check
```
GET /rca-v2/health
```

## Comparison: v1 vs v2

| Feature | v1 (Original) | v2 (State Machine) |
|---------|---------------|-------------------|
| State Management | Simple dict | RCAStateMachine class |
| LLM Context | Full conversation history | Controlled, curated context |
| Memory Updates | LLM can influence | Orchestrator-only |
| Memory Types | Mixed in single dict | Separate ExecutionMemory + ControlMemory |
| State Transitions | Ad-hoc in loops | Validated state machine |
| Error Handling | Basic try/catch | State-based error handling |
| Stopping Logic | Mixed conditions | Clear StopReason enum |
| Context Control | LLM decides | Orchestrator decides |

## Usage Examples

### Basic Analysis
```python
from Agents.rca_v2.agent import RCAOrchestratorV2
from Agents.rca_v2.schemas import WhyAnalysisInput

orchestrator = RCAOrchestratorV2()

input_data = WhyAnalysisInput(
    complaint_id="CAPA-2026-001",
    complaint="Temperature sensor readings were inconsistent",
    fmea_document_path="fmea.xlsx"
)

result = orchestrator.analyze(input_data)
```

### State Machine Inspection
```python
# During execution, you can inspect state
state_machine = RCAStateMachine(...)

print(f"Current State: {state_machine.get_current_state()}")
print(f"Should Continue: {state_machine.should_continue()}")
print(f"Execution Memory: {len(state_machine.execution_memory.iterations)} iterations")
print(f"State Transitions: {state_machine.execution_memory.state_transitions}")
```

## Benefits

1. **Predictable Behavior**: State machine ensures consistent execution flow
2. **Controlled Memory**: LLM never sees full history, only relevant context
3. **Better Debugging**: State transitions and memory changes are logged
4. **Separation of Concerns**: Clear boundaries between execution, control, and LLM context
5. **Error Recovery**: Proper error states and handling
6. **Audit Trail**: Complete state transition history for compliance

## Migration from v1

The v2 API is compatible with v1 - same input/output schemas. Simply change the endpoint:

- v1: `POST /why-analysis/`
- v2: `POST /rca-v2/`

The v1 endpoint remains available for backward compatibility during your demo.