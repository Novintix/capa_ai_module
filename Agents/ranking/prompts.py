"""
Ranking Agent Prompts - Configurable for any domain
Contains prompt templates that adapt to different contexts and scenarios.

Key principle: All 3 LLM scores (evidence, mechanism, proximity) are collected
in a SINGLE LLM call per cause using a unified JSON prompt, rather than 3 sequential calls.
This reduces LLM calls from 3N → N for N causes.
"""


def build_scores_prompt(cause_text: str, issue_type: str, context_step: str, impact_description: str, domain: str = "generic", evidence_context: str = "investigation", mechanism_context: str = "technical analysis", proximity_context: str = "causal analysis") -> str:
    """
    Build a unified prompt that returns all 3 scoring dimensions in a single LLM call.
    Replaces 3 separate prompts (evidence, mechanism, proximity) with 1 combined prompt.

    Args:
        cause_text: Description of the potential cause
        issue_type: Type of issue/failure
        context_step: Context/process step where issue occurs
        impact_description: Impact/effects of the issue
        domain: Domain context (e.g., 'manufacturing', 'software', 'healthcare')
        evidence_context: Context label for evidence evaluation
        mechanism_context: Context label for mechanism evaluation
        proximity_context: Context label for proximity evaluation

    Returns:
        Prompt string for LLM — expects a single JSON object in response
    """
    return f"""You are an expert {domain} analyst performing root cause analysis scoring ({evidence_context}, {mechanism_context}, {proximity_context}).

Evaluate the cause below and return a JSON object with EXACTLY these 3 fields:

{{
  "evidence_strength": <one of: 1.0, 0.7, 0.5, 0.3>,
  "mechanism_fit":    <one of: 0.9, 0.7, 0.4>,
  "causal_proximity": <one of: 1.0, 0.7, 0.4>
}}

SCORING CRITERIA:

evidence_strength — What type of direct support exists for this cause?
  1.0 = Observable : Direct data, logs, measurements, inspection records, system outputs
  0.7 = Indirect   : Human observations, visual checks, reported symptoms, sampling data
  0.5 = Historical : Previous cases, maintenance records, past incidents, trend data
  0.3 = None       : No supporting evidence, speculation, assumptions only

mechanism_fit — How strongly does this cause explain the failure through {domain} principles?
  0.9 = Strong     : Cause directly and clearly explains the issue
  0.7 = Moderate   : Cause partially explains the issue, some logical connection exists
  0.4 = Weak       : Cause weakly or indirectly relates to the issue

causal_proximity — How directly does this cause trigger the issue?
  1.0 = Direct     : Immediate trigger, no intermediate steps
  0.7 = Contributor: Secondary factor, one intermediate step
  0.4 = Background : Distant cause, multiple intermediate steps

CAUSE TO EVALUATE:
Domain      : {domain}
Cause       : {cause_text}
Issue Type  : {issue_type}
Context Step: {context_step}
Impact      : {impact_description}

RULES:
- Return ONLY valid JSON — no explanations, no markdown, no text outside the JSON object
- Each field must be exactly one of the allowed values listed above
- Be deterministic — same input always produces same output"""


# ---------------------------------------------------------------------------
# Legacy single-dimension prompt builders (kept for reference / backward compat)
# These are NO LONGER used by the main nodes — use build_scores_prompt instead.
# ---------------------------------------------------------------------------

def build_evidence_prompt(cause_text: str, issue_type: str, context_step: str, domain: str = "generic", evidence_context: str = "investigation") -> str:
    """DEPRECATED: Use build_scores_prompt instead."""
    return build_scores_prompt(
        cause_text=cause_text, issue_type=issue_type, context_step=context_step,
        impact_description="", domain=domain, evidence_context=evidence_context
    )


def build_mechanism_prompt(cause_text: str, issue_type: str, impact_description: str, domain: str = "generic", mechanism_context: str = "technical analysis") -> str:
    """DEPRECATED: Use build_scores_prompt instead."""
    return build_scores_prompt(
        cause_text=cause_text, issue_type=issue_type, context_step="",
        impact_description=impact_description, domain=domain, mechanism_context=mechanism_context
    )


def build_proximity_prompt(cause_text: str, issue_type: str, context_step: str, domain: str = "generic", proximity_context: str = "causal analysis") -> str:
    """DEPRECATED: Use build_scores_prompt instead."""
    return build_scores_prompt(
        cause_text=cause_text, issue_type=issue_type, context_step=context_step,
        impact_description="", domain=domain, proximity_context=proximity_context
    )
