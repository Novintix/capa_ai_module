import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict

class RiskAnalysisState(TypedDict, total=False):

    # ── Input ─────────────────────────────────────────────────────────────────
    raw_input:          str

    # ── Validation ────────────────────────────────────────────────────────────
    validation_passed:  bool
    validation_error:   Optional[str]

    # ── Context Extraction layer (context_node) ───────────────────────────────
    urgency:            bool
    extracted:          dict        # raw LLM extraction result

    # ── Payload layer (payload_builder_node only) ─────────────────────────────
    enriched_inputs:    dict        # per-agent tailored payloads

    # ── Parallel agent results ─────────────────────────────────────────────────
    # Annotated reducer — all 4 agents append safely in parallel
    agent_results:      Annotated[list, operator.add]

    # ── RPN scores (written by A4) ─────────────────────────────────────────────
    severity_score:     Optional[int]
    severity_label:     Optional[str]
    detection_score:    Optional[int]
    occurrence_score:   Optional[int]
    rpn_value:          Optional[float]
    rpn_level:          Optional[str]

    # ── Downstream outputs ─────────────────────────────────────────────────────
    regulatory_output:  Optional[dict]
    reasoning_output:   Optional[dict]

    # ── Final ─────────────────────────────────────────────────────────────────
    final_report:       Optional[dict]

    # ── Audit ─────────────────────────────────────────────────────────────────
    # Annotated reducer — every node appends its log safely
    node_log:           Annotated[list, operator.add]
    errors:             Annotated[list, operator.add]
