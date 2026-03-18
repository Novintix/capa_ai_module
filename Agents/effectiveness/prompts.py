"""
prompts.py

Prompt builder for CAPA Effectiveness Evaluation generation.
"""

def build_effectiveness_evaluation_prompt(evaluation_input: dict) -> str:
    actions_str = ""
    for action in evaluation_input.get("actions", []):
        actions_str += f"- ID: {action.get('action_id')}, Description: {action.get('action_description')}\n"

    return f"""You are an Expert CAPA Effectiveness Evaluation Agent.

Your objective is to evaluate the effectiveness of proposed or implemented corrective and preventive actions in resolving the identified root cause and preventing recurrence of the issue.

Task:
Given a root cause and a list of corrective or preventive actions, analyze how effectively each action addresses the root cause, prevents recurrence, and improves system reliability. Assign an effectiveness score to each action and rank them accordingly.

-----------------------------------
INPUT PROVIDED:
-----------------------------------
- Root Cause Description: {evaluation_input.get('root_cause_description', 'N/A')}
- Corrective or Preventive Actions:
{actions_str}
- System Context: {evaluation_input.get('system_context', 'N/A')}
- Supporting Evidence: {evaluation_input.get('supporting_evidence', 'N/A')}
- Effectiveness Evaluation Criteria: {evaluation_input.get('effectiveness_evaluation_criteria', 'Use standard criteria')}

Evaluation Criteria (total score out of 100):
- Root Cause Coverage (0–40): Evaluate whether the action directly addresses or eliminates the root cause.
- Recurrence Prevention Capability (0–30): Assess how effectively the action prevents the issue from occurring again.
- Impact on System Reliability (0–20): Determine how much the action improves system stability, safety, or performance.
- Implementation Feasibility (0–10): Evaluate whether the action is practical and implementable within the system constraints.

Reasoning Process:
1. Analyze the identified root cause.
2. Evaluate each corrective or preventive action against the root cause.
3. Determine how strongly the action mitigates or eliminates the root cause.
4. Assess the likelihood that the action prevents recurrence.
5. Evaluate the operational impact of the action on system performance.
6. Calculate an overall effectiveness score.
7. Rank actions from highest to lowest effectiveness.

Constraints:
- Base evaluations only on provided inputs and evaluation criteria.
- Use explainable reasoning for every score.
- If insufficient data is available, indicate reduced confidence.
- Do not assume implementation success without supporting evidence.

-----------------------------------
OUTPUT FORMAT (MANDATORY)
-----------------------------------
Return ONLY valid JSON. No explanations, no reasoning, no markdown. The format MUST be:

{{
  "evaluated_actions": [
    {{
      "action_id": "<Action ID>",
      "action_description": "<Action Description>",
      "root_cause_addressed": "<Yes|Partially|No>",
      "recurrence_prevention_level": "<High|Medium|Low>",
      "system_impact": "<High|Medium|Low>",
      "effectiveness_score": <int 0-100>,
      "confidence_level": "<High|Medium|Low>",
      "explanation_of_evaluation": "<detailed explanation based on criteria>"
    }}
  ],
  "confidence_score": <0.0-1.0>,
  "notes": "<additional notes or null>"
}}

Ensure the `evaluated_actions` list is ordered from highest `effectiveness_score` to lowest. Return ONLY JSON, nothing else.
"""
