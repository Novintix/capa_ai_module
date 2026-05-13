"""
nodes.py

Processing nodes for CAPA Effectiveness Evaluation Agent.

Nodes:
  1. extract_evidence_node     — parses uploaded file, merges with JSON text
  2. evaluate_actions_node     — LLM scores each CAPA action
  3. validate_evaluations_node — GxP guardrail checks with retry support

Evidence Input Cases (handled in Node 1):
  Case 1 — File only          : extract from file, use as supporting_evidence
  Case 2 — Text only          : use JSON supporting_evidence as-is
  Case 3 — Both               : file takes priority, JSON text appended as supplementary
  Case 4 — Neither            : empty string, LLM evaluates with reduced confidence
"""

import io
import json_repair
from .state import EffectivenessState
from config.aws_bedrock_config import get_llm
from .prompts import build_effectiveness_evaluation_prompt
from .model import EffectivenessEvaluationResponse
from .tools.pdf_extractor import extract_text_from_pdf
from .tools.excel_extractor import extract_text_from_excel
from .tools.csv_extractor import extract_text_from_csv
from .tools.word_extractor import extract_text_from_word
from .tools.image_extractor import extract_text_from_image
from .logger import (
    logger,
    log_node_entry,
    log_node_exit,
    log_error,
    log_evaluation,
    log_validation_pass,
)

MAX_RETRIES = 3


# ── Node 1: Extract Evidence ─────────────────────────────────────────────────

def extract_evidence_node(state: EffectivenessState) -> EffectivenessState:
    """
    NODE 1: Extract and merge supporting evidence.

    Case 1 — File only (no text in JSON):
        Extract text from file → set as supporting_evidence

    Case 2 — Text only (no file uploaded):
        supporting_evidence from JSON used as-is, no extraction needed

    Case 3 — Both file and text provided:
        File takes priority → extracted text first
        JSON text appended as supplementary context section

    Case 4 — Neither provided:
        supporting_evidence set to empty string
        LLM evaluates with reduced confidence (reflected in output scores)
    """
    log_node_entry("extract_evidence_node", state)
    state["error"] = None

    try:
        file_bytes       = state.get("evidence_file_bytes")
        file_name        = state.get("evidence_file_name")
        evaluation_input = state.get("evaluation_input", {})
        existing_text    = (evaluation_input.get("supporting_evidence") or "").strip()

        # Case 2: Text only
        if not file_bytes or not file_name:
            if existing_text:
                logger.info(
                    f"[EXTRACT NODE] Case 2: Text only — "
                    f"using JSON supporting_evidence ({len(existing_text)} chars)."
                )
            else:
                # Case 4: Neither
                logger.warning(
                    "[EXTRACT NODE] Case 4: No file and no supporting_evidence text. "
                    "Evaluation will proceed with reduced confidence."
                )
                evaluation_input["supporting_evidence"] = ""
                state["evaluation_input"] = evaluation_input

            log_node_exit("extract_evidence_node", state)
            return state

        # Case 1 or 3: File present — route to correct extractor by extension
        import tempfile
        ext = file_name.strip().lower().rsplit(".", 1)[-1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        if ext == "pdf":
            extracted_text = extract_text_from_pdf(tmp_path)
        elif ext in ("xlsx", "xls"):
            extracted_text = extract_text_from_excel(tmp_path)
        elif ext == "csv":
            extracted_text = extract_text_from_csv(tmp_path)
        elif ext == "docx":
            extracted_text = extract_text_from_word(tmp_path)
        elif ext in ("jpg", "jpeg", "png", "bmp", "tiff"):
            extracted_text = extract_text_from_image(tmp_path)
        else:
            raise ValueError(f"Unsupported file type: .{ext}. Supported: pdf, xlsx, xls, csv, docx, jpg, png, bmp, tiff")

        import os
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        extracted_text = extracted_text or ""
        state["extracted_evidence_text"] = extracted_text

        if existing_text:
            # Case 3: Both — merge
            merged = (
                f"{extracted_text}\n\n"
                f"--- Supplementary Evidence (from JSON input) ---\n"
                f"{existing_text}"
            )
            evaluation_input["supporting_evidence"] = merged
        else:
            # Case 1: File only
            evaluation_input["supporting_evidence"] = extracted_text

        state["evaluation_input"] = evaluation_input

        log_node_exit("extract_evidence_node", state)
        return state

    except Exception as e:
        log_error("extract_evidence_node", str(e))
        state["error"] = str(e)
        raise


# ── Node 2: Evaluate Actions ─────────────────────────────────────────────────

def evaluate_actions_node(state: EffectivenessState) -> EffectivenessState:
    """
    NODE 2: LLM evaluates each CAPA action for effectiveness.
    On retry, injects the prior guardrail violation into the prompt for self-correction.
    """
    log_node_entry("evaluate_actions_node", state)
    state["error"] = None

    try:
        llm                      = get_llm()
        evaluation_input         = state.get("evaluation_input", {})
        validation_error_message = state.get("validation_error_message", None)

        prompt = build_effectiveness_evaluation_prompt(
            evaluation_input,
            validation_error_message=validation_error_message
        )

        response    = llm.invoke(prompt)
        content     = response.content
        parsed_json = json_repair.loads(content)
        if isinstance(parsed_json, str):
            parsed_json = json_repair.loads(parsed_json)

        validated_response = EffectivenessEvaluationResponse(**parsed_json)

        state["evaluated_actions"] = [
            item.model_dump() for item in validated_response.evaluated_actions
        ]
        state["evaluated_actions"].sort(
            key=lambda x: x["effectiveness_score"], reverse=True
        )

        state["confidence_score"]         = validated_response.confidence_score
        state["notes"]                    = validated_response.notes
        state["validation_error_message"] = None

        log_evaluation(state["evaluated_actions"])
        log_node_exit("evaluate_actions_node", state)
        return state

    except Exception as e:
        log_error("evaluate_actions_node", str(e))
        state["error"] = str(e)
        raise


# ── Node 3: Validate Evaluations ─────────────────────────────────────────────

def validate_evaluations_node(state: EffectivenessState) -> EffectivenessState:
    """
    NODE 3: GxP guardrail validation.
    All 6 guardrails must pass. On failure, stores violation for retry prompt.
    """
    log_node_entry("validate_evaluations_node", state)
    state["error"]                    = None
    state["validation_error_message"] = None

    try:
        evaluated_actions = state.get("evaluated_actions", [])

        for action in evaluated_actions:
            score       = action.get("effectiveness_score", 0)
            addressed   = action.get("root_cause_addressed", "No")
            recurrence  = action.get("recurrence_prevention_level", "Low")
            confidence  = action.get("confidence_level", "Low")
            explanation = action.get("explanation_of_evaluation", "").strip()
            action_id   = action.get("action_id", "Unknown")

            # G1: Score range — max is 95, never 100
            if score < 0 or score > 95:
                raise ValueError(
                    f"Action {action_id}: score={score} is out of bounds. "
                    f"Valid range is 0-95. Score of 100 is never allowed in "
                    f"post-implementation review."
                )

            # G2: root_cause_addressed=No caps score at 40
            if addressed == "No" and score > 40:
                raise ValueError(
                    f"Action {action_id}: root_cause_addressed='No' but score={score}. "
                    f"Must be <= 40."
                )

            # G3: root_cause_addressed=Partially caps score at 75
            if addressed == "Partially" and score > 75:
                raise ValueError(
                    f"Action {action_id}: root_cause_addressed='Partially' but score={score}. "
                    f"Must be <= 75."
                )

            # G4: root_cause_addressed=Yes must score at least 50
            if addressed == "Yes" and score < 50:
                raise ValueError(
                    f"Action {action_id}: root_cause_addressed='Yes' but score={score}. "
                    f"A fully addressed root cause must score >= 50."
                )

            # G5: recurrence_prevention=Low caps score at 60
            if recurrence == "Low" and score > 60:
                raise ValueError(
                    f"Action {action_id}: recurrence_prevention_level='Low' but score={score}. "
                    f"Must be <= 60."
                )

            # G6: recurrence_prevention=High must score at least 60
            if recurrence == "High" and score < 60:
                raise ValueError(
                    f"Action {action_id}: recurrence_prevention_level='High' but score={score}. "
                    f"High recurrence prevention must score >= 60."
                )

            # G7: root_cause=No → recurrence MUST be Low
            if addressed == "No" and recurrence != "Low":
                raise ValueError(
                    f"Action {action_id}: root_cause_addressed='No' but "
                    f"recurrence_prevention_level='{recurrence}'. "
                    f"If root cause is not addressed, recurrence prevention MUST be 'Low'. "
                    f"An action cannot prevent recurrence of a root cause it does not address."
                )

            # G8: root_cause=Yes → recurrence cannot be Low
            if addressed == "Yes" and recurrence == "Low":
                raise ValueError(
                    f"Action {action_id}: root_cause_addressed='Yes' but "
                    f"recurrence_prevention_level='Low'. "
                    f"A fully addressed root cause must have at least Medium recurrence prevention."
                )

            # G9: confidence=Low caps score at 79
            if confidence == "Low" and score >= 80:
                raise ValueError(
                    f"Action {action_id}: confidence_level='Low' but score={score} >= 80. "
                    f"Low confidence requires score < 80."
                )

            # G10: confidence=High must score at least 30
            if confidence == "High" and score < 30:
                raise ValueError(
                    f"Action {action_id}: confidence_level='High' but score={score} < 30. "
                    f"High confidence with evidence cannot produce a very low score."
                )

            # G11: Score >= 85 requires Yes + High + High
            if score >= 85 and (
                addressed  != "Yes" or
                recurrence != "High" or
                confidence != "High"
            ):
                raise ValueError(
                    f"Action {action_id}: score={score} >= 85 but "
                    f"root_cause_addressed='{addressed}', "
                    f"recurrence_prevention_level='{recurrence}', "
                    f"confidence_level='{confidence}'. "
                    f"Scores >= 85 require all three to be 'Yes', 'High', 'High'."
                )

            # G12: Explanation minimum length
            if len(explanation) < 50:
                raise ValueError(
                    f"Action {action_id}: explanation too short ({len(explanation)} chars). "
                    f"Minimum 50 chars required for GxP audit compliance."
                )

            # G13: Explanation must contain at least one specific evidence reference
            # Accepts: numbers, percentages, named IDs, dates, or frequency/temporal words
            # (e.g. "quarterly" is a concrete fact when the evidence itself has no digits)
            import re
            has_evidence_ref = bool(re.search(
                r'\d+|%|TECH-\d+|SOP-\d+|[A-Z]+-\d+|\d{2}-[A-Za-z]+-\d{4}'
                r'|\b(?:daily|weekly|monthly|quarterly|annually|bi-annual|semi-annual|annual|hourly)\b',
                explanation,
                re.IGNORECASE
            ))
            if not has_evidence_ref:
                raise ValueError(
                    f"Action {action_id}: explanation_of_evaluation contains no specific "
                    f"evidence references (numbers, dates, IDs, percentages). "
                    f"Must cite at least one concrete fact from the implementation evidence."
                )

        log_validation_pass(evaluated_actions)
        log_node_exit("validate_evaluations_node", state)
        return state

    except ValueError as e:
        violation_msg = str(e)
        log_error("validate_evaluations_node", violation_msg)
        state["validation_error_message"] = violation_msg
        state["error"]                    = violation_msg
        raise