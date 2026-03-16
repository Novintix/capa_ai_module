# Cause Generation Agent

## What This Agent Does
Generates a list of possible causes for "why" questions by analyzing FMEA documents or using expert knowledge when FMEA is unavailable. The agent filters out irrelevant causes using LLM validation to ensure only relevant causes are returned.

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
3. Parse FMEA          7. Process with LLM
   ↓                      (Generate causes)
4. Parse Question          ↓
   ↓                    8. Finalize
5. Match FMEA             ↓
   ↓                   Output: Generated causes
6. Extract Causes
   ↓
7. Process with LLM
   (Validate/filter causes)
   ↓
8. Finalize
   ↓
Output: Validated relevant causes
```

**Single LLM Call**: The agent now uses LLM only once - either for validation (when FMEA exists) or generation (when FMEA doesn't exist).

