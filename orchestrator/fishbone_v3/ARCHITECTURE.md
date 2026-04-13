# Fishbone V3 Architecture

## Overview
Fishbone V3 is a Human-in-the-Loop (HITL) root cause analysis system that combines multiple AI agents with human decision-making.

## Components

### 1. State Machine (`state_machine.py`)
**Purpose**: Manages workflow state and data flow

**States**:
```
INITIALIZING 
    ↓
LISTING_CAUSES (Find potential causes)
    ↓
CATEGORIZING (Assign 6M categories)
    ↓
VALIDATING (Match against evidence)
    ↓
WAIT_FOR_HUMAN (Pause for human decision)
    ↓
RECORDING_DECISIONS (Record human choices)
    ↓
ANALYSIS_COMPLETE
```

**Memory Types**:
- `IterationMemory`: Stores causes, validation results, category summary
- `ExecutionMemory`: Tracks state transitions, timestamps
- `ControlMemory`: Current state, execution trace, stop reason

### 2. Orchestrator Agent (`agent.py`)
**Purpose**: Coordinates all agents and manages HITL flow

**Methods**:
- `analyze()`: Phase 1 - Run analysis up to validation, return WAIT_FOR_HUMAN
- `submit_decisions()`: Phase 2 - Process human decisions, complete analysis

**Agent Calls**:
1. ListCausesAgent (cause_generation) - Extract causes from FMEA/LLM
2. CategorizationAgent (categorize) - Assign 6M categories
3. ValidationAgent (validation) - Match causes against evidence
4. ZeroEvidenceAgent (zero_evidence) - Rank causes when no high confidence

### 3. Session Memory (`session_memory.py`)
**Purpose**: Redis-based persistence for HITL workflow

**Functions**:
- Save state between analyze() and submit_decisions()
- Store all causes (including low confidence) for later retrieval
- TTL: 1 hour (configurable)

### 4. Router (`router.py`)
**Purpose**: FastAPI endpoints

**Endpoints**:
- `POST /fishbone-v3/analyze` - Start analysis
- `POST /fishbone-v3/decide` - Submit human decisions

## Data Flow

```
User Input (complaint, evidence, FMEA)
    ↓
ListCausesAgent → [C001, C002, C003, ...]
    ↓
CategorizationAgent → Add 6M categories (Man, Machine, Method, Material, Measurement, Environment)
    ↓
ValidationAgent → Add validation_status (matched/partially_matched/no_evidence) + confidence (0.0-1.0)
    ↓
Filter: confidence ≥ 0.9 AND status == "matched"
    ↓
IF high_confidence_causes exist:
    → WAIT_FOR_HUMAN (save to Redis)
    → Human decides: PROCEED or RCA
    → submit_decisions() → COMPLETED
ELSE:
    → ZeroEvidenceAgent ranks all causes
    → COMPLETED
```

## High Confidence Criteria

A cause qualifies for human review if:
1. `validation_confidence >= 0.9` (90%+)
2. `validation_status == "matched"` (not partially_matched or no_evidence)

## Validation Confidence Alignment

The system enforces confidence ranges based on evidence status:
- `matched`: 70-100% confidence
- `partially_matched`: 30-80% confidence
- `no_evidence`: 0-30% confidence

This prevents the LLM from assigning high confidence to causes without evidence.

## Why Results Vary

**LLM Non-Determinism**: AI models can produce different outputs for the same input due to:
- Temperature setting (randomness)
- Model sampling
- Context window variations

**To Reduce Variability**:
1. Set temperature=0 in LLM config (more deterministic)
2. Use consistent prompts
3. Cache results for same inputs
4. Use seed values (if supported by model)

## UI Flow

1. User submits complaint → `analyze()`
2. System shows all stages:
   - Stage 1: All Causes Found
   - Stage 2: Categorized (6M)
   - Stage 3: Validated Against Evidence
   - Stage 4: High Confidence (requires decision)
   - Stage 5: Zero Evidence Ranking (if no high confidence)
3. Fishbone diagram shows all causes color-coded by validation status
4. User makes decisions (PROCEED/RCA) → auto-submits → `submit_decisions()`
5. Final results displayed
