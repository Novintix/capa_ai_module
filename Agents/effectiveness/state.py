"""
state.py

Defines EffectivenessState for CAPA Effectiveness Evaluation LangGraph workflow.
"""

from typing import TypedDict, Optional, List, Dict, Any


class EffectivenessState(TypedDict, total=False):
    """State passed through effectiveness graph nodes."""

    # ── Input ────────────────────────────────────────────────────────────────
    evaluation_input: Dict[str, Any]

    # ── Evidence file (optional upload) ──────────────────────────────────────
    evidence_file_bytes:     Optional[bytes]   # raw uploaded file bytes
    evidence_file_name:      Optional[str]     # filename with extension
    extracted_evidence_text: Optional[str]     # parsed plain text from file

    # ── Processing results ────────────────────────────────────────────────────
    evaluated_actions: Optional[List[Dict[str, Any]]]
    confidence_score:  Optional[float]
    notes:             Optional[str]

    # ── Retry control ─────────────────────────────────────────────────────────
    retry_count:              int
    validation_error_message: Optional[str]

    # ── Error tracking ────────────────────────────────────────────────────────
    error: Optional[str]