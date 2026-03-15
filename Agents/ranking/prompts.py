"""
Ranking Agent Prompts - Configurable for any domain
Contains prompt templates that adapt to different contexts and scenarios
"""


def build_evidence_prompt(cause_text: str, issue_type: str, context_step: str, domain: str = "generic", evidence_context: str = "investigation") -> str:
    """
    Build domain-adaptive prompt for evidence strength evaluation.
    
    Args:
        cause_text: Description of the potential cause
        issue_type: Type of issue/failure
        context_step: Context/process step where issue occurs
        domain: Domain context (e.g., 'manufacturing', 'software', 'healthcare')
        evidence_context: Context for evidence evaluation
        
    Returns:
        Prompt string for LLM
    """
    return f"""You are an expert analyst evaluating evidence strength for {domain} {evidence_context}.

CRITICAL RULES:
1. Assign EXACTLY ONE score from: 1.0, 0.7, 0.5, or 0.3
2. Return ONLY the numeric score as a single number
3. No explanations, no markdown, no text outside the number
4. Be deterministic - same input always produces same output

EVIDENCE SCORING CRITERIA:
- 1.0 (Observable): Direct data, logs, measurements, inspection records, system outputs
- 0.7 (Indirect): Human observations, visual checks, reported symptoms, sampling data
- 0.5 (Historical): Previous cases, maintenance records, past incidents, trend data
- 0.3 (None): No supporting evidence, speculation, assumptions only

CONTEXT TO EVALUATE:
Domain: {domain}
Cause: {cause_text}
Issue Type: {issue_type}
Context: {context_step}

INSTRUCTIONS:
Analyze what type of evidence would typically support this cause in the {domain} domain.
Consider the context and issue type when determining evidence availability.
Return ONLY ONE number: 1.0, 0.7, 0.5, or 0.3"""


def build_mechanism_prompt(cause_text: str, issue_type: str, impact_description: str, domain: str = "generic", mechanism_context: str = "technical analysis") -> str:
    """
    Build domain-adaptive prompt for mechanism fit evaluation.
    
    Args:
        cause_text: Description of the potential cause
        issue_type: Type of issue/failure
        impact_description: Impact/effects of the issue
        domain: Domain context
        mechanism_context: Context for mechanism evaluation
        
    Returns:
        Prompt string for LLM
    """
    return f"""You are an expert analyst evaluating mechanism relationships for {domain} {mechanism_context}.

CRITICAL RULES:
1. Assign EXACTLY ONE score from: 0.9, 0.7, or 0.4
2. Return ONLY the numeric score as a single number
3. No explanations, no markdown, no text outside the number
4. Be deterministic - same input always produces same output

MECHANISM FIT SCORING CRITERIA:
- 0.9 (Strong): Cause directly and clearly explains the issue through established {domain} principles
- 0.7 (Moderate): Cause partially explains the issue, some logical connection exists
- 0.4 (Weak): Cause weakly or indirectly relates to issue, unclear mechanism

CONTEXT TO EVALUATE:
Domain: {domain}
Cause: {cause_text}
Issue Type: {issue_type}
Impact: {impact_description}

INSTRUCTIONS:
Analyze the logical relationship between the cause and issue in the {domain} context.
Consider whether the cause logically and directly leads to the observed issue.
Evaluate the strength of the causal mechanism based on {domain} principles.
Return ONLY ONE number: 0.9, 0.7, or 0.4"""


def build_proximity_prompt(cause_text: str, issue_type: str, context_step: str, domain: str = "generic", proximity_context: str = "causal analysis") -> str:
    """
    Build domain-adaptive prompt for causal proximity evaluation.
    
    Args:
        cause_text: Description of the potential cause
        issue_type: Type of issue/failure
        context_step: Context/process step where issue occurs
        domain: Domain context
        proximity_context: Context for proximity evaluation
        
    Returns:
        Prompt string for LLM
    """
    return f"""You are an expert analyst evaluating causal proximity for {domain} {proximity_context}.

CRITICAL RULES:
1. Assign EXACTLY ONE score from: 1.0, 0.7, or 0.4
2. Return ONLY the numeric score as a single number
3. No explanations, no markdown, no text outside the number
4. Be deterministic - same input always produces same output

CAUSAL PROXIMITY SCORING CRITERIA:
- 1.0 (Direct): Immediate trigger, directly causes the issue with no intermediate steps
- 0.7 (Contributor): Secondary factor, contributes to issue through one intermediate step
- 0.4 (Background): Distant cause, indirect relationship with multiple intermediate steps

CONTEXT TO EVALUATE:
Domain: {domain}
Cause: {cause_text}
Issue Type: {issue_type}
Context: {context_step}

INSTRUCTIONS:
Analyze the causal chain from the cause to the issue in the {domain} context.
Count the number of intermediate steps between cause and effect.
Determine if the cause is an immediate trigger, contributing factor, or background condition.
Return ONLY ONE number: 1.0, 0.7, or 0.4"""
