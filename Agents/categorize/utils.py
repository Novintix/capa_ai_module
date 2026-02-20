from typing import List, Dict
from Agents.categorize.state import Cause
from Agents.categorize.prompts import CATEGORIZE_PROMPT_TEMPLATE

def build_causes_block(causes: List[Cause]) -> str:
    """Build formatted causes block for prompt."""
    lines = []
    for idx, cause in enumerate(causes, 1):
        lines.append(f"{idx}. **{cause.cause_id}**: {cause.cause_text}")
        lines.append(f"   - Process Step: {cause.process_step}")
        lines.append(f"   - Failure Mode: {cause.failure_mode}")
        lines.append(f"   - Current Controls: {cause.current_controls or 'None'}")
        lines.append("")
    return "\n".join(lines)

def build_prompt(question: str, causes: List[Cause], context: str = "None") -> str:
    """Build the full categorization prompt."""
    causes_block = build_causes_block(causes)
    
    return CATEGORIZE_PROMPT_TEMPLATE.format(
        question=question,
        context=context,
        causes_block=causes_block
    )

def calculate_summary(categorizations: List) -> Dict[str, int]:
    """Calculate count per category. Includes both primary and secondary categories."""
    summary = {
        "Man": 0,
        "Machine": 0,
        "Method": 0,
        "Material": 0,
        "Measurement": 0,
        "Environment": 0,
        "Unknown": 0
    }
    
    for cat in categorizations:
        # Count primary category
        if cat.category in summary:
            summary[cat.category] += 1
        # Count secondary categories
        for secondary in cat.secondary_categories:
            if secondary in summary:
                summary[secondary] += 1
    
    return summary
