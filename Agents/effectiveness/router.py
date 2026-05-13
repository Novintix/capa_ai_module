"""
router.py

FastAPI route for CAPA Effectiveness Evaluation Agent.

Content-Type : multipart/form-data (always)

Form fields:
  - root_cause_description         : str  (required)
  - actions                        : str  (required) — JSON array string
  - system_context                 : str  (required)
  - supporting_evidence            : str  (optional) — plain text
  - effectiveness_evaluation_criteria : str (optional)
  - evidence_file                  : file (optional) — .pdf .docx .xlsx .xls .json .csv .txt

Supporting evidence cases:
  Case 1 — File only  : upload evidence_file, leave supporting_evidence empty
  Case 2 — Text only  : fill supporting_evidence, no file upload
  Case 3 — Both       : file takes priority, text appended as supplementary
  Case 4 — Neither    : evaluates with reduced confidence
"""

import json
from fastapi import APIRouter, HTTPException, Depends, File, Form, UploadFile
from typing import Optional

from .graph import build_graph
from .model import EffectivenessEvaluationInput, EffectivenessEvaluationResponse
from .logger import logger
from agent_ops import agentops_session

router = APIRouter()


def get_graph():
    """FastAPI dependency — fresh graph per request."""
    return build_graph()


@router.post("/effectiveness", response_model=EffectivenessEvaluationResponse)
@agentops_session(name="Effectiveness_Evaluation", tags=["agents", "effectiveness"])
async def evaluate_effectiveness(
    # ── Required form fields ─────────────────────────────────────────────────
    root_cause_description: str = Form(
        ...,
        description="Root cause description"
    ),
    actions: str = Form(
        ...,
        description='JSON array string. e.g. [{"action_id":"CA-01","action_description":"..."}]'
    ),
    system_context: str = Form(
        ...,
        description="System context — process, area, or environment"
    ),
    # ── Optional form fields ─────────────────────────────────────────────────
    supporting_evidence: Optional[str] = Form(
        None,
        description="Supporting evidence as plain text (optional if file is uploaded)"
    ),
    effectiveness_evaluation_criteria: Optional[str] = Form(
        None,
        description="Scoring criteria (uses default if omitted)"
    ),

    # ── Optional file upload ──────────────────────────────────────────────────
    evidence_file: Optional[UploadFile] = File(
        None,
        description="Evidence file (.pdf, .docx, .xlsx, .xls, .json, .csv, .txt)"
    ),
    graph=Depends(get_graph)
):
    """
    Evaluate CAPA Action Plan effectiveness.
    Content-Type: multipart/form-data

    Send each field individually as a form field — no JSON wrapping needed.
    The 'actions' field is the only one that requires a JSON array string.
    """

    # ── Parse actions JSON string ─────────────────────────────────────────────
    try:
        actions_list = json.loads(actions)
        if not isinstance(actions_list, list):
            raise ValueError("actions must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=422,
            detail=f"'actions' field is not a valid JSON array: {str(e)}"
        )

    # ── Build and validate evaluation input ───────────────────────────────────
    try:
        evaluation_input = EffectivenessEvaluationInput(
            root_cause_description=root_cause_description,
            actions=actions_list,
            system_context=system_context,
            supporting_evidence=supporting_evidence or None,
            effectiveness_evaluation_criteria=(
                effectiveness_evaluation_criteria
                or "Evaluate based on Root Cause Coverage (0-40), "
                   "Recurrence Prevention Capability (0-30), "
                   "Impact on System Reliability (0-20), "
                   "Implementation Feasibility (0-10)."
            )
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Input validation error: {str(e)}")

    # ── Read file bytes if uploaded ───────────────────────────────────────────
    file_bytes = None
    file_name  = None

    if evidence_file and evidence_file.filename:
        file_bytes = await evidence_file.read()
        file_name  = evidence_file.filename

    # ── Log evidence case ─────────────────────────────────────────────────────
    existing_text = (evaluation_input.supporting_evidence or "").strip()

    if file_bytes and existing_text:
        logger.info(
            f"[ROUTER] Case 3: Both | File: {file_name} ({len(file_bytes)} bytes) "
            f"+ Text ({len(existing_text)} chars). File takes priority."
        )
    elif file_bytes:
        logger.info(f"[ROUTER] Case 1: File only | {file_name} | {len(file_bytes)} bytes")
    elif existing_text:
        logger.info(f"[ROUTER] Case 2: Text only | {len(existing_text)} chars")
    else:
        logger.warning("[ROUTER] Case 4: No evidence. Reduced confidence evaluation.")

    # ── Invoke graph ──────────────────────────────────────────────────────────
    try:
        result = graph.invoke({
            "evaluation_input":         evaluation_input.model_dump(),
            "evidence_file_bytes":      file_bytes,
            "evidence_file_name":       file_name,
            "extracted_evidence_text":  None,
            "retry_count":              0,
            "validation_error_message": None,
            "error":                    None,
        })

        return EffectivenessEvaluationResponse(
            evaluated_actions=result.get("evaluated_actions", []),
            confidence_score=result.get("confidence_score", 0.0),
            notes=result.get("notes")
        )

    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))