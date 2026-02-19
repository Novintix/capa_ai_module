import json
import re
from Agents.aireasoning.state import AIReasoningState, AIReasoningResponse
from Agents.aireasoning.utils import build_prompt, build_evidence_summary
from config.aws_bedrock_config import get_llm
from Agents.aireasoning.logger import (
    log_prompt, log_raw_response, log_error,
    log_node_start, log_node_end
)


MAX_ITERATIONS = 3


def prepare_evidence(state: AIReasoningState) -> dict:
    """
    Node 1: Pre-computes evidence summary from input data.
    """
    log_node_start("prepare_evidence")

    if state.iteration >= MAX_ITERATIONS:
        log_node_end("prepare_evidence", "MAX_ITERATIONS reached — aborting")
        raise RuntimeError(f"Max iteration limit ({MAX_ITERATIONS}) reached.")

    input_data = state.input

    evidence_summary = build_evidence_summary(
        risk_score=input_data.risk_score,
        pattern=input_data.pattern,
        severity_level=input_data.severity_level,
        nc_source=input_data.nc_source,
        regulatory_impact=input_data.regulatory_impact,
        customer_impact=input_data.customer_impact,
        additional_data=input_data.additional_data
    )

    num_additional_fields = len(input_data.additional_data) if input_data.additional_data else 0
    log_node_end("prepare_evidence", f"Evidence summary built with {num_additional_fields} additional data fields")

    return {
        "iteration": state.iteration + 1,
        "evidence_summary": evidence_summary
    }


def generate_reasoning(state: AIReasoningState) -> dict:
    """
    Node 2: Calls LLM to generate AI reasoning based on evidence.
    """
    log_node_start("generate_reasoning")

    input_data = state.input
    evidence_summary = state.evidence_summary

    if evidence_summary is None:
        evidence_summary = build_evidence_summary(
            risk_score=input_data.risk_score,
            pattern=input_data.pattern,
            severity_level=input_data.severity_level,
            nc_source=input_data.nc_source,
            regulatory_impact=input_data.regulatory_impact,
            customer_impact=input_data.customer_impact,
            additional_data=input_data.additional_data
        )

    prompt = build_prompt(
        complaint_id=input_data.complaint_id,
        risk_score=input_data.risk_score,
        pattern=input_data.pattern,
        severity_level=input_data.severity_level,
        nc_source=input_data.nc_source,
        regulatory_impact=input_data.regulatory_impact,
        customer_impact=input_data.customer_impact,
        additional_context=input_data.additional_context or "None",
        evidence_summary=evidence_summary
    )

    log_prompt(prompt)

    try:
        llm = get_llm()
        response = llm.invoke(prompt)

        log_raw_response(response.raw_content)

        raw_content = response.content
        json_match = re.search(r'({.*})', raw_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_content

        content = json.loads(json_str)
        reasoning_response = AIReasoningResponse(**content)

        log_node_end("generate_reasoning", "AI reasoning generated successfully")

        return {"raw_reasoning": reasoning_response}

    except Exception as e:
        log_error("generate_reasoning", str(e))
        raise RuntimeError(f"Error generating reasoning: {str(e)}")


def finalize_output(state: AIReasoningState) -> dict:
    """
    Node 3: Validates raw_reasoning and finalizes the output.
    """
    log_node_start("finalize_output")

    reasoning = state.raw_reasoning
    if not reasoning:
        raise ValueError("State guard failed: raw_reasoning is None before finalize_output")

    log_node_end("finalize_output", f"Confidence: {reasoning.confidence_level}")

    return {"final_output": reasoning}
