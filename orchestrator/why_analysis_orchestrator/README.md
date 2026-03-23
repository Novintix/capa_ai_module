# Why Analysis Orchestrator

## Overview

The Why Analysis Orchestrator is a comprehensive agent that conducts root cause analysis by orchestrating three specialized agents in sequence. It implements the "5 Whys" methodology with intelligent cause generation and ranking to identify the most critical functional cause of a problem.

## What This Agent Does

The orchestrator performs systematic root cause analysis by:

1. **Generating Progressive Why Questions** - Creates contextual "Why?" questions that dig deeper into the problem
2. **Finding/Generating Causes** - Uses FMEA documents or LLM to identify potential causes for each question
3. **Ranking and Selecting Causes** - Applies criticality scoring to select the most critical cause at each level
4. **Iterating Until Root Cause Found** - Continues the process until no more causes are found or maximum depth is reached

## Architecture Flow

```
Input (Complaint + Evidence + SOP) 
    ↓
┌─────────────────────────────────────────────────────────────┐
│                 Why Analysis Orchestrator                    │
│                                                             │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   Question  │ →  │ Cause Generation│ →  │Zero Evidence│ │
│  │   Generator │    │     Agent       │    │    Agent    │ │
│  │             │    │                 │    │             │ │
│  │ Generates   │    │ • FMEA Matching │    │ • Criticality│ │
│  │ "Why?"      │    │ • LLM Fallback  │    │   Scoring   │ │
│  │ questions   │    │ • Semantic      │    │ • Risk      │ │
│  │             │    │   Similarity    │    │   Assessment│ │
│  └─────────────┘    └─────────────────┘    └─────────────┘ │
│         ↑                                         │         │
│         └─────────── Iteration Loop ──────────────┘         │
└─────────────────────────────────────────────────────────────┘
    ↓
Output (Root Cause + Detailed Iteration History)
```

## Operating Modes

### 1. FMEA Iterative Mode
- **Trigger**: `fmea_document_path` is provided
- **Behavior**: Iterates through Why questions until FMEA causes are exhausted or max depth reached
- **Cause Source**: FMEA document matching with LLM validation
- **Confidence**: HIGH (when multiple iterations completed)

### 2. No-FMEA Single-Shot Mode  
- **Trigger**: `fmea_document_path` is omitted
- **Behavior**: Single iteration with LLM-generated causes
- **Cause Source**: Pure LLM generation based on problem context
- **Confidence**: MEDIUM (single iteration, no FMEA validation)

## Why Context is Needed

The orchestrator requires comprehensive context for effective analysis:

- **Complaint**: Defines the specific problem to analyze
- **Evidence**: Provides factual observations that guide question generation and cause validation
- **SOP**: Establishes the expected process flow to identify deviations
- **FMEA Document**: Contains documented failure modes and causes for systematic analysis

This context enables the orchestrator to:
1. Generate relevant and focused Why questions
2. Validate causes against actual evidence
3. Prioritize causes based on process criticality
4. Maintain consistency with established procedures

## Key Features

- **No Redis Dependency**: Self-contained question generation using LLM
- **Comprehensive Error Handling**: Graceful fallbacks for all failure scenarios
- **Detailed Iteration Tracking**: Complete visibility for UI display
- **Execution Time Monitoring**: Performance tracking for optimization
- **Dynamic Field Support**: Handles any FMEA column structure
- **Semantic Matching**: Advanced cause-to-question relevance scoring
- **Cause Deduplication**: Prevents repetition of same causes across iterations
- **Intelligent Stopping**: Detects when no deeper analysis is possible
- **Minimal Input Requirements**: Only complaint_id and complaint are required

## Input Requirements

### Required Fields
- `complaint_id`: Unique identifier for tracking
- `complaint`: Problem statement to analyze

### Optional Fields
- `evidence`: Supporting facts and observations (defaults to empty string)
- `sop`: Relevant standard operating procedure (defaults to empty string)
- `fmea_document_path`: Path to FMEA Excel file (enables iterative mode)
- `max_depth`: Maximum Why iterations (default: 5)

## Output Structure

The orchestrator provides comprehensive results including:

- **Root Cause**: Complete details of the selected most critical cause
- **Confidence Level**: LOW/MEDIUM/HIGH based on analysis depth and source
- **Analysis Mode**: Which operating mode was used
- **Iteration History**: Detailed tracking of each Why level with:
  - Questions asked
  - Causes found and analyzed
  - Selection reasoning
  - FMEA matches
  - Generation methods

## Error Handling

The orchestrator handles multiple failure scenarios:

- **FMEA File Not Found**: Falls back to LLM generation
- **No Causes Generated**: Stops iteration gracefully
- **Agent Communication Failures**: Provides detailed error context
- **Invalid Input Data**: Clear validation error messages

## Performance Characteristics

- **Single LLM Call per Iteration**: Optimized for cost and speed
- **Lazy Agent Initialization**: Reduces startup time
- **Efficient FMEA Parsing**: Cached document processing
- **Structured Logging**: Comprehensive audit trail for debugging