# Zero Evidence Agent

## Purpose

Activated when no validation evidence, observable signals, or historical data exists.
Determines the **Most Critical Functional Cause** from the provided FMEA cause list using
**first-principles reasoning and composite criticality scoring** — without generating new causes.

---

## Architecture

```
initialize
    │
validate_input          ← Guard: reject empty cause list
    │
llm_evaluate            ← Bedrock LLM: evaluates single-point failure + safety risk per cause
    │
score_causes            ← Deterministic formula (no LLM):
    │                      0.4×severity + 0.2×SPF + 0.2×sys_dep + 0.2×safety
select_cause            ← Picks the single highest-scored cause
    │
finalize ──► END
```

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/zero-evidence/` | Run analysis |
| GET | `/zero-evidence/health` | Health check |
