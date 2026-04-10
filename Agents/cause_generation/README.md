# Cause Generation Agent

## What This Agent Does
Generates a list of possible causes for "why" questions by analyzing FMEA documents or using expert knowledge when FMEA is unavailable. The agent filters out irrelevant causes using LLM validation and assigns Severity, Occurrence, and Detection scores based on context.

## Architecture Flow

```
Input: "Why was the syringe marking incorrect?"
   ↓
1. Initialize → Set up processing state
   ↓
2. Validate FMEA → Check if FMEA document exists
   ↓                    ↓
   FMEA Available       FMEA Not Available
   ↓                    ↓
3. Parse FMEA          8. Process with LLM
   ↓                      (Generate causes)
4. Parse Question          ↓
   ↓                    9. Score Causes
5. Extract from Evidence   (LLM assigns S/O/D)
   ↓                       ↓
6. Match FMEA           10. Finalize
   ↓                       ↓
7. Extract Causes       Output: Generated & scored causes
   ↓
8. Process with LLM
   (Validate/filter causes)
   ↓
9. Score Causes
   (LLM assigns Severity/Occurrence/Detection)
   ↓
10. Finalize
    (Calculate confidence)
   ↓
Output: Validated, scored, relevant causes
```

**LLM Calls**: 
- First LLM call: Validation (filter FMEA causes) or Generation (create causes)
- Second LLM call: Scoring (assign Severity, Occurrence, Detection based on context)

## Key Features

### No Hardcoded Values
- All Severity, Occurrence, and Detection scores are assigned by LLM based on:
  - Question context
  - Evidence context (logs, reports, investigation records)
  - Process step and failure mode information
  - Source reliability (Evidence > FMEA > Generated)

### Dynamic Confidence Calculation
- Confidence is calculated based on:
  - Source mix (evidence-based causes have higher confidence)
  - Score completeness (all causes properly scored)
  - Number of causes (more causes = slightly lower confidence)

### Context-Aware Scoring
- Evidence-based causes: Higher severity/occurrence if failure already occurred
- FMEA causes: Uses existing scores or assigns new ones based on context
- Generated causes: Scores based on typical industry patterns and question context

