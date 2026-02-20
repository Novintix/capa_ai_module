import json
import re
from typing import List
from Agents.categorize.state import CategorizeState, CategorizedCause, CategorizeOutput
from Agents.categorize.utils import build_prompt, calculate_summary
from config.aws_bedrock_config import get_llm
from Agents.categorize.logger import (
    log_prompt, log_raw_response, log_error,
    log_node_start, log_node_end
)

MAX_RETRIES = 3

def categorize_causes(state: CategorizeState) -> dict:
    """
    Node: Calls LLM to categorize causes into 6M categories.
    Retries up to MAX_RETRIES if LLM fails or returns invalid JSON.
    """
    if state.iteration == 0:
        from Agents.categorize.logger import clear_logs
        clear_logs()
    
    log_node_start("categorize_causes")
    
    input_data = state.input
    
    if state.iteration > MAX_RETRIES:
        error_msg = f"Max retries ({MAX_RETRIES}) reached for categorize_causes. Aborting."
        log_error("categorize_causes", error_msg)
        raise RuntimeError(error_msg)
    
    prompt = build_prompt(
        question=input_data.question,
        causes=input_data.causes,
        context=input_data.additional_context or "None"
    )
    
    log_prompt(prompt)
    
    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        
        log_raw_response(response.content, run_number=state.iteration + 1)
        
        # Extract JSON
        raw_content = response.content
        json_match = re.search(r'({.*})', raw_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_content
        
        content = json.loads(json_str)
        
        # Parse categorizations
        # Defensively ensure secondary_categories is always present
        categorizations = []
        for item in content.get("categorizations", []):
            item.setdefault("secondary_categories", [])
            categorizations.append(CategorizedCause(**item))
        
        log_node_end("categorize_causes", f"Categorized {len(categorizations)} causes")
        
        return {"raw_categorizations": categorizations}
    
    except Exception as e:
        log_error("categorize_causes", f"Attempt {state.iteration + 1} failed: {str(e)}")
        return {"iteration": state.iteration + 1}


def build_output(state: CategorizeState) -> dict:
    """
    Node: Builds final output with summary statistics.
    """
    log_node_start("build_output")
    
    categorizations = state.raw_categorizations
    if not categorizations:
        raise ValueError("State guard failed: raw_categorizations is None before build_output")
    
    summary = calculate_summary(categorizations)
    
    output = CategorizeOutput(
        categorized_causes=categorizations,
        summary=summary
    )
    
    log_node_end("build_output", f"Summary: {summary}")
    
    return {"final_output": output}
