"""
Cause Generation Agent Prompts
Single LLM prompt for cause validation or generation
"""


# =============================================================================
# UNIFIED CAUSE PROCESSING PROMPT
# =============================================================================

CAUSE_PROCESSING_SYSTEM_ROLE = """You are a CAUSE ANALYSIS EXPERT specializing in manufacturing and quality control processes.

YOUR ROLE:
- Analyze "why" questions and provide relevant causes
- Filter out irrelevant causes when FMEA data is provided
- Generate expert causes when no FMEA data is available
- Apply logical reasoning for cause-effect relationships

YOUR EXPERTISE:
- Manufacturing processes and failure modes
- Root cause analysis methodologies
- Process step interdependencies
- Quality control systems"""

CAUSE_PROCESSING_TASK_INSTRUCTIONS = """TASK: Based on the input provided, either validate FMEA causes or generate expert causes.

WHEN FMEA CAUSES ARE PROVIDED:
- Filter out causes that are NOT directly related to the question
- Keep only causes with logical cause-effect relationships
- Remove causes from unrelated process steps

WHEN NO FMEA CAUSES ARE PROVIDED:
- Generate 3-5 most likely causes for the problem
- Include process-related, material-related, and human-related causes
- Provide realistic severity, occurrence, and detection ratings (1-10)
- Focus on actionable causes teams can investigate
- CRITICAL: Keep cause_text SHORT and FOCUSED (3-8 words max)
- Each cause should describe ONE specific issue only
- Examples: "Calibration checklist outdated", "Operator training inadequate", "Pump seal worn"
- Avoid long explanations or multiple concepts in one cause"""

CAUSE_PROCESSING_OUTPUT_FORMAT = """OUTPUT REQUIREMENTS:
- Return ONLY valid JSON format
- No explanations, reasoning, or markdown

FOR FMEA VALIDATION:
{
  "mode": "validation",
  "relevant_cause_numbers": [1, 2, 3],
  "reasoning": "Brief explanation of filtering"
}

FOR CAUSE GENERATION:
{
  "mode": "generation",
  "causes": [
    {
      "cause_text": "Short focused description (3-8 words)",
      "process_step": "Relevant process step",
      "failure_mode": "How it manifests",
      "potential_effects": "Impact if not addressed",
      "severity": 7,
      "occurrence": 3,
      "detection": 4,
      "current_controls": "Typical controls",
      "source": "Generated"
    }
  ]
}

IMPORTANT FOR CAUSE_TEXT:
- Keep it SHORT: 3-8 words maximum
- ONE specific issue per cause
- Clear and actionable
- Good examples: "Calibration procedure not followed", "Operator training inadequate", "Equipment maintenance overdue"
- Bad examples: Long sentences with multiple concepts or detailed explanations"""

def get_unified_cause_prompt(question: str, causes_text: str = None) -> str:
    """
    Build unified prompt for either validation or generation
    
    Args:
        question: The original why question
        causes_text: Optional formatted list of FMEA causes to validate
        
    Returns:
        Complete prompt for LLM
    """
    if causes_text:
        # Validation mode
        task_specific = f"""MODE: VALIDATION
Filter the provided FMEA causes to keep only those relevant to the question.

QUESTION: {question}

FMEA CAUSES TO VALIDATE:
{causes_text}

Return validation JSON with relevant_cause_numbers array."""
    else:
        # Generation mode
        task_specific = f"""MODE: GENERATION
Generate possible causes for the problem since no FMEA document is available.

QUESTION: {question}

CRITICAL REQUIREMENTS FOR CAUSE_TEXT:
- ONE specific issue only
- No long explanations
- Focus on the core problem
- Examples: "Training inadequate", "Checklist outdated", "Equipment not calibrated"

Generate expert causes JSON with causes array."""
    
    return f"""{CAUSE_PROCESSING_SYSTEM_ROLE}

{CAUSE_PROCESSING_TASK_INSTRUCTIONS}

{CAUSE_PROCESSING_OUTPUT_FORMAT}

{task_specific}"""


# =============================================================================
# UTILITIES
# =============================================================================

def format_causes_for_validation(causes: list) -> str:
    """
    Format causes list for validation prompt
    
    Args:
        causes: List of cause dictionaries
        
    Returns:
        Formatted string for prompt
    """
    causes_text = ""
    for i, cause in enumerate(causes, 1):
        causes_text += f"{i}. Process: {cause.get('process_step', 'N/A')}\n"
        causes_text += f"   Cause: {cause.get('cause_text', 'N/A')}\n"
        causes_text += f"   Failure Mode: {cause.get('failure_mode', 'N/A')}\n\n"
    
    return causes_text.strip()


def validate_prompt_inputs(question: str) -> bool:
    """
    Validate prompt inputs before sending to LLM
    
    Args:
        question: The why question
        
    Returns:
        True if inputs are valid
    """
    return bool(question and question.strip())