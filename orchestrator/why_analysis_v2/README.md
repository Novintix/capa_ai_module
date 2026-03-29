# Why Analysis V2 Orchestrator

## Overview

Why Analysis V2 is a looped RCA orchestrator that enforces this exact sequence:

1. Question Agent
2. Cause Generation Agent
3. Validation Agent
4. Loop Control Agent

Conditional routing rules:

- If validation returns more than one valid cause, run Ranking Agent to choose one cause, then continue to Loop Control.
- If validation returns exactly one valid cause, skip Ranking and pass that cause directly to Loop Control.
- If validation returns zero valid causes, run Zero Evidence Mode Agent and stop immediately as AI flagged.

Loop behavior:

- If Loop Control returns `STOP_ROOT_FOUND`, analysis stops with confirmed root cause.
- If Loop Control returns `LOOP`, selected cause is sent to Question Agent (`/why/continue` semantics) and next loop starts.
- If Loop Control returns `STOP_DEGRADED`, analysis stops and marks manual investigation required.

Default loop cap is 10.

## API

- `POST /why-analysis-v2/`
- `GET /why-analysis-v2/health`

## Python Entry

- `WhyAnalysisV2Orchestrator.analyze(input_data)` in `agent.py`

## Input

Core fields:

- `complaint_id`
- `complaint`
- `evidence` (optional)
- `sop` (optional)
- `fmea_document_path` (optional)
- `max_loops` (optional, default 10)

Validation evidence fields are also accepted:

- `evidence_files`
- `logs`
- `reports`
- `process_data`
- `historical_capa`
- `policies`
- `investigation_records`
- `supporting_system_information`

## Output

Key fields in `WhyAnalysisV2Output`:

- `status`
- `mode`
- `analysis_depth`
- `ai_flagged`
- `manual_investigation_required`
- `stopping_reason`
- `root_cause`
- `why_chain`
- `validation_summary`
- `loop_control_summary`
- `execution_time_seconds`
- `error`

## Notes

- The orchestrator calls agent classes directly, not over HTTP.
- It uses `complaint_id` as the chain key for Question Agent Redis-backed continuation.
- It keeps existing `why-analysis` endpoints untouched and exposes a separate `why-analysis-v2` route.
