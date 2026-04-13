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


# =============================================================================
# DEDUPLICATION PROMPT
# =============================================================================

DEDUPLICATION_SYSTEM_ROLE = """You are a CAUSE DEDUPLICATION EXPERT specializing in identifying duplicate or semantically identical causes.

YOUR ROLE:
- Analyze a list of causes and identify duplicates
- Recognize when causes describe the same root issue with different wording
- Keep only unique causes, removing redundant ones
- Preserve the most specific and actionable version of each cause

DUPLICATE DETECTION CRITERIA:
1. **Exact duplicates**: Same wording
2. **Semantic duplicates**: Same meaning, different words
3. **Subset duplicates**: One cause is a more specific version of another
4. **Paraphrases**: Different phrasing of the same issue

EXAMPLES OF DUPLICATES:
- "Compression force set incorrectly" ≈ "Compression force was set at 12kN instead of specified 10kN"
- "Operator setup error" ≈ "Operator made setup mistake"
- "Training inadequate" ≈ "Insufficient operator training"
- "Equipment not calibrated" ≈ "Calibration not performed"

KEEP THE BETTER VERSION:
- More specific > More generic
- Evidence-based > FMEA-based
- Actionable > Vague"""

DEDUPLICATION_TASK_INSTRUCTIONS = """TASK: Review the list of causes and remove duplicates.

RULES:
1. Compare each cause with all others
2. If two causes describe the same issue, keep only ONE
3. When choosing which to keep:
   - Prefer evidence-based causes over FMEA causes
   - Prefer more specific descriptions over generic ones
   - Prefer causes with higher severity/occurrence scores
4. Return ONLY the unique causes
5. Preserve all original fields for kept causes

IMPORTANT:
- Be strict about duplicates - if causes are semantically the same, they are duplicates
- Don't be fooled by different wording - focus on the underlying issue
- A cause that is a more detailed version of another is a duplicate (keep the detailed one)"""

DEDUPLICATION_OUTPUT_FORMAT = """OUTPUT FORMAT:
Return ONLY valid JSON with unique causes:

{
  "unique_causes": [
    {
      "cause_id": "C001",
      "cause_text": "...",
      "process_step": "...",
      "failure_mode": "...",
      "potential_effects": "...",
      "severity": 7,
      "occurrence": 5,
      "detection": 6,
      "current_controls": "...",
      "source": "..."
    }
  ],
  "removed_duplicates": [
    {
      "removed_cause_id": "C003",
      "removed_cause_text": "...",
      "duplicate_of": "C001",
      "reason": "Same issue as C001 but less specific"
    }
  ],
  "total_input": 10,
  "total_unique": 7,
  "total_removed": 3
}"""


def get_deduplication_prompt(causes: list) -> str:
    """
    Build prompt for deduplicating causes
    
    Args:
        causes: List of cause dictionaries to deduplicate
        
    Returns:
        Complete prompt for LLM deduplication
    """
    # Build causes list
    causes_text = ""
    for cause in causes:
        causes_text += f"\nCause ID: {cause.get('cause_id', 'Unknown')}\n"
        causes_text += f"Cause Text: {cause.get('cause_text', 'N/A')}\n"
        causes_text += f"Process Step: {cause.get('process_step', 'N/A')}\n"
        causes_text += f"Failure Mode: {cause.get('failure_mode', 'N/A')}\n"
        causes_text += f"Source: {cause.get('source', 'Unknown')}\n"
        causes_text += f"Severity: {cause.get('severity', 'N/A')}\n"
        causes_text += "---\n"
    
    return f"""{DEDUPLICATION_SYSTEM_ROLE}

{DEDUPLICATION_TASK_INSTRUCTIONS}

{DEDUPLICATION_OUTPUT_FORMAT}

CAUSES TO DEDUPLICATE ({len(causes)} total):{causes_text}

Analyze these causes carefully and return ONLY the JSON with unique causes and removed duplicates."""


# =============================================================================
# SCORING PROMPT (SEVERITY, OCCURRENCE, DETECTION)
# =============================================================================

SCORING_SYSTEM_ROLE = """You are a RISK ASSESSMENT EXPERT specializing in FMEA (Failure Mode and Effects Analysis).

YOUR ROLE:
- Evaluate causes and assign Severity, Occurrence, and Detection scores
- Use context from evidence, question, and cause description
- Apply FMEA scoring standards (1-10 scale)

SCORING CRITERIA:

SEVERITY (Impact of failure):
1-3: Minor impact, no safety risk, minimal customer impact
4-6: Moderate impact, some customer dissatisfaction, repairable
7-8: High impact, significant customer dissatisfaction, safety concern
9-10: Critical impact, safety hazard, regulatory violation, product recall

OCCURRENCE (Likelihood of cause happening):
1-2: Remote probability, rarely happens
3-4: Low probability, isolated failures
5-6: Moderate probability, occasional failures
7-8: High probability, repeated failures
9-10: Very high probability, failure is almost inevitable

DETECTION (Ability to detect before reaching customer):
1-2: Almost certain detection, multiple controls in place
3-4: High detection probability, good controls
5-6: Moderate detection, some controls
7-8: Low detection probability, weak controls
9-10: Almost no detection, no controls, reaches customer"""

SCORING_TASK_INSTRUCTIONS = """TASK: Assign Severity, Occurrence, and Detection scores to each cause based on context.

CONTEXT CONSIDERATIONS:
- Evidence-based causes (from logs/reports): Higher severity and occurrence if already occurred
- FMEA causes: Use process step and failure mode context
- Generated causes: Use question context and typical industry patterns
- If evidence shows the failure already happened: Occurrence should be higher (6-9)
- If evidence shows it reached customer/production: Detection should be higher (7-10)

IMPORTANT:
- Scores must be integers from 1 to 10
- Consider the specific context provided
- Be realistic and consistent
- Higher scores = higher risk"""

SCORING_OUTPUT_FORMAT = """OUTPUT FORMAT:
Return ONLY valid JSON array with scores for each cause:

[
  {
    "cause_id": "C001",
    "severity": 7,
    "occurrence": 5,
    "detection": 6,
    "reasoning": "Brief explanation of scoring"
  },
  {
    "cause_id": "C002",
    "severity": 8,
    "occurrence": 7,
    "detection": 8,
    "reasoning": "Brief explanation of scoring"
  }
]"""


def get_scoring_prompt(question: str, causes: list, evidence_context: dict = None) -> str:
    """
    Build prompt for scoring causes with Severity, Occurrence, Detection
    
    Args:
        question: The original why question
        causes: List of cause dictionaries to score
        evidence_context: Optional evidence context for better scoring
        
    Returns:
        Complete prompt for LLM scoring
    """
    # Build causes list
    causes_text = ""
    for cause in causes:
        causes_text += f"\nCause ID: {cause.get('cause_id', 'Unknown')}\n"
        causes_text += f"Cause Text: {cause.get('cause_text', 'N/A')}\n"
        causes_text += f"Process Step: {cause.get('process_step', 'N/A')}\n"
        causes_text += f"Failure Mode: {cause.get('failure_mode', 'N/A')}\n"
        causes_text += f"Source: {cause.get('source', 'Unknown')}\n"
        
        # Include existing scores if available (for reference)
        if cause.get('severity'):
            causes_text += f"Existing Severity: {cause.get('severity')}\n"
        if cause.get('occurrence'):
            causes_text += f"Existing Occurrence: {cause.get('occurrence')}\n"
        if cause.get('detection'):
            causes_text += f"Existing Detection: {cause.get('detection')}\n"
        causes_text += "---\n"
    
    # Build evidence context
    evidence_text = ""
    if evidence_context:
        if evidence_context.get("evidence"):
            evidence_text += f"\nEVIDENCE: {evidence_context['evidence']}\n"
        
        if evidence_context.get("logs"):
            evidence_text += f"\nLOGS: {len(evidence_context['logs'])} log entries available\n"
            for log in evidence_context.get("logs", [])[:3]:  # First 3 logs
                if isinstance(log, dict):
                    evidence_text += f"  - {log.get('message', '')}\n"
        
        if evidence_context.get("reports"):
            evidence_text += f"\nREPORTS: {len(evidence_context['reports'])} reports available\n"
            for report in evidence_context.get("reports", [])[:2]:  # First 2 reports
                if isinstance(report, dict):
                    evidence_text += f"  - {report.get('summary', '')}\n"
    
    if not evidence_text:
        evidence_text = "\nNo evidence context provided. Use general industry knowledge for scoring.\n"
    
    return f"""{SCORING_SYSTEM_ROLE}

{SCORING_TASK_INSTRUCTIONS}

{SCORING_OUTPUT_FORMAT}

QUESTION: {question}

EVIDENCE CONTEXT:{evidence_text}

CAUSES TO SCORE:{causes_text}

Return ONLY the JSON array with scores for each cause."""