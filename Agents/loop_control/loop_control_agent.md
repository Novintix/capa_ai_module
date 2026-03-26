# Loop Control Agent - Implementation Notes

## Purpose
This agent is the final gate in the Why-analysis flow. It decides whether the current cause is a true root cause or whether the analysis should continue with another why-loop.

## Current Behavior Summary
- Primary outcomes in current logic:
  - `STOP_ROOT_FOUND`
  - `LOOP`
- `STOP_DEGRADED` remains in the schema enum for compatibility, but the active decision path currently returns root-or-loop.

## Input Schema
Defined in `state.py` as `LoopControlInput`:
- `incident_description: str`
- `current_loop_count: int`
- `max_loops: int`
- `current_top_cause: str`
- `current_cause_confidence: float`
- `fmea_document_path: Optional[str]` (present for compatibility, not used in current decision logic)
- `full_why_chain: list[WhyChainItem]` where each item has:
  - `loop`
  - `question`
  - `cause`
  - `confidence`

## Graph Flow
Implemented in `graph.py`:
1. `evaluate_chain`
2. `decide`
3. `finalize_output`

## Step-by-Step Logic

### 1. Chain Health (Deterministic)
Implemented in `utils.py`:
- Circular check:
  - Token-overlap with prior causes.
  - Circular is true if overlap ratio > 0.55.
- Specificity trend:
  - Scores causes using component/config/number signals vs abstract noun penalties.
  - Trend classified as `increasing`, `stable`, or `decreasing`.
- Confidence trend:
  - Computed from chain confidence values.

### 2. Root Assessment (Single Strong LLM Call)
Implemented in `_assess_root_cause` with prompt from `build_root_assessment_prompt`:
- LLM returns strict JSON fields:
  - `is_root_cause`
  - `actionability` (1-3)
  - `system_depth` (1-3)
  - `chain_resolution` (1-3)
  - `incident_alignment` (`strong` | `weak` | `none`)
  - `confidence`
  - `rationale`
- Prompt enforces hard constraints:
  - Local condition statements (for example low temperature, drift, wrong setting) are not systemic root by themselves.
  - Root must align to incident and resolve prior why-chain.

### 3. Deterministic Depth Calibration
After LLM scoring, code calibrates `system_depth`:
- If systemic terms exist (process/policy/SOP/governance/standard work), depth is lifted toward 3.
- If local condition terms exist (temperature/pressure/drift/sensor/setting), depth is capped at 2.
- If symptom-only terms exist (operator error/human error/mistake), depth is capped toward 1.

### 4. Final Decision (Deterministic)
Implemented in `decide`:
- If chain degraded (`circular` and `specificity_trend == decreasing`) -> `LOOP`.
- If alignment is `none` -> `LOOP`.
- Compute:
  - `total = actionability + system_depth + recurrence_prevention`
  - `adjusted_total = total - 1` when alignment is `weak`, else unchanged.
- Root gate requires systemic depth:
  - `system_depth >= 3`
  - `recurrence_prevention >= 2`
  - `actionability >= 2`
  - confidence threshold check (`current_cause_confidence >= 0.7`)
  - score threshold (`adjusted_total >= 7`)
- Strong shortcut:
  - If `system_depth >= 3` and `recurrence_prevention == 3` and alignment is `strong` -> `STOP_ROOT_FOUND`.
- Otherwise -> `LOOP` and generate next-step guidance.

## Next-Step Generation (When LOOP)
When decision is `LOOP`, the agent calls `build_next_step_prompt` and returns:
- `probe_angle` (`configuration` | `detection` | `change` | `load` | `process`)
- `avoid`
- `evidence_hint`

If next-step LLM output fails, a deterministic fallback next step is produced.

## Error Handling
- Root-assessment LLM calls are strict JSON parsed.
- Parsing/invocation failure raises errors at runtime (fail-fast behavior).
- Router returns HTTP 500 on unhandled processing exceptions.

## Output Schema
`LoopControlOutput` contains:
- `decision`
- `reasoning`
- `chain_health`
- `root_cause_score`
- `next_step` (only populated when decision is `LOOP`)

## Practical Interpretation
The current implementation intentionally avoids stopping at local operational conditions and pushes toward systemic root statements (process/policy/SOP/governance/standard-work flaws) before returning `STOP_ROOT_FOUND`.
