"""
orchestrator_service/state.py

RiskAnalysisState — single source of truth for all orchestrator state.

Fields are grouped by layer:
  Input → Validation → Correction → Extraction → Payloads →
  Agent Results → RPN → Downstream → Final → Audit
"""

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class RiskAnalysisState(TypedDict, total=False):

    # ── Input ─────────────────────────────────────────────────────────────────
    raw_input:              str
    complaint_id:           Optional[str]   # business-level ID — set by context_node from extracted data

    # ── Structured input (optional — bypasses context_node LLM extraction) ────
    # When provided by the UI from MongoDB-backed complaint data, context_node
    # is skipped and these fields are mapped directly into `extracted`.
    enriched_input:         Optional[dict]  # keys mirror EXTRACTION_PROMPT enriched fields

    # ── Validation ────────────────────────────────────────────────────────────
    validation_passed:      bool
    validation_error:       Optional[str]
    validation_category:    Optional[str]   # complaint | manufacturing_nc | safety_event
                                            # | malicious | irrelevant | error | terminated

    # ── Correction loop ───────────────────────────────────────────────────────
    # Set by input_validator on soft failure.
    # Cleared by /capa/correct before re-invoking.
    awaiting_correction:    Optional[bool]  # True = paused, waiting for user to fix input
    correction_message:     Optional[str]   # human-readable message shown to user / Postman
    correction_count:       Optional[int]   # how many correction attempts have been used
    correction_response:    Optional[dict]  # full payload written by request_correction_node
                                            # → read by router.py and returned as API response

    # ── Context extraction (context_node) ─────────────────────────────────────
    urgency:                bool
    extracted:              dict            # raw LLM extraction result

    # ── Payload layer (payload_builder_node only) ──────────────────────────────
    enriched_inputs:        dict            # per-agent tailored payloads

    # ── Parallel agent results ─────────────────────────────────────────────────
    # Annotated reducer — all 4 parallel agents append safely in parallel
    agent_results:          Annotated[list, operator.add]

    # ── RPN scores ────────────────────────────────────────────────────────────
    severity_score:         Optional[int]
    severity_label:         Optional[str]
    detection_score:        Optional[int]
    occurrence_score:       Optional[int]
    rpn_value:              Optional[float]
    rpn_level:              Optional[str]   # CRITICAL | HIGH | MEDIUM | LOW

    # ── Downstream outputs ────────────────────────────────────────────────────
    regulatory_output:      Optional[dict]
    reasoning_output:       Optional[dict]

    # ── Final ─────────────────────────────────────────────────────────────────
    final_report:           Optional[dict]

    # ── Audit ─────────────────────────────────────────────────────────────────
    # Annotated reducer — every node appends its log entry safely
    node_log:               Annotated[list, operator.add]
    errors:                 Annotated[list, operator.add]