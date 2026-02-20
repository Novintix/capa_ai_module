# Cause Generation Agent

## Purpose
Generates list of all possible causes for "why" questions by parsing FMEA documents and using hybrid matching (keywords + semantic embeddings).

## Agent Type
Deterministic, document-driven agent with optional semantic matching. No LLM usage.

## Responsibilities
- Parse FMEA Excel documents
- Extract keywords from "why" questions
- Match questions to FMEA entries using hybrid approach:
  - Keyword matching (fast, exact)
  - Semantic similarity using embeddings (intelligent, fuzzy)
- Return ALL possible causes from matched entries
- Provide causes with full FMEA metadata for downstream validation/ranking


## Flow
1. **Initialize**: Set up state
2. **Validate FMEA**: Check if FMEA document exists
3. **Parse FMEA**: Extract structured data from Excel
4. **Parse Question**: Extract keywords from why question
5. **Match FMEA**: Hybrid matching (keyword + semantic similarity)
6. **Extract Causes**: Retrieve all causes from matched rows
7. **Finalize**: Return structured result with cause list

## Matching Strategy
1. **Keyword Matching**: Fast exact/partial text matching
2. **Semantic Matching**: Uses sentence-transformers embeddings for semantic similarity
3. **Hybrid**: Combines both for best results
4. **Fallback**: Returns all FMEA causes if no match found

## Input
- `question_id`: Unique identifier
- `question`: Why question (e.g., "Why did the bike stop?", "Why is tablet strength incorrect?")
- `context`: Optional context from previous 5-Why analysis
- `fmea_path`: Path to FMEA Excel document

## Output
- `question`: Original why question
- `causes`: List of all possible causes with:
  - `cause_id`: Unique identifier
  - `cause_text`: Cause description
  - `process_step`: Associated process
  - `failure_mode`: Associated failure
  - `potential_effects`: Effects from FMEA
  - `severity`, `occurrence`, `detection`: FMEA ratings
  - `current_controls`: Existing controls
  - `source`: "FMEA"
- `total_causes`: Count of causes
- `matched_entries`: Number of FMEA rows matched
- `confidence`: Match confidence (0-1)
- `notes`: Matching method used

## FMEA Format
Expected Excel columns:
- Process Step / Risk Identification
- Potential Failure Mode
- Potential Effects
- Potential Causes
- Severity
- Occurrence
- Detection / Detection Level
- Current Process Control


