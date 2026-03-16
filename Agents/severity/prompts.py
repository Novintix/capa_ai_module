"""
prompts.py

Severity Agent prompt builder.

Design decisions to reduce hallucination:
  1. Matrix injected as a clear numbered table (not raw JSON) so the LLM
     can read and match it reliably.
  2. Explicit chain-of-thought reasoning field added — forces the LLM to
     think before scoring, which reduces arbitrary or inflated scores.
  3. Strict grounding rules: "default LOW unless evidence says otherwise"
     prevents the LLM from guessing HIGH when there is no patient harm.
  4. Few-shot examples anchor the LLM to expected score ranges.
"""


def _format_matrix_as_table(matrix: dict) -> str:
    """
    Converts the raw matrix dict into a clean numbered table.
    Much easier for an LLM to match than a JSON blob.
    """
    lines = []
    for score, dims in matrix.items():
        lines.append(
            f"  Score {score}:\n"
            f"    Clinical      : {dims['clinical']}\n"
            f"    Reversibility : {dims['reversibility']}\n"
            f"    Medical       : {dims['medical']}\n"
            f"    Duration      : {dims['duration']}"
        )
    return "\n".join(lines)


def build_severity_prompt(issue: str, matrix: dict) -> str:
    matrix_table = _format_matrix_as_table(matrix)
    return f"""You are a regulated medical device clinical safety evaluator.
Your task is to assign a severity score for each of the four dimensions below,
strictly based on the Severity Matrix definitions provided.

════════════════════════════════════════════════════════════
SEVERITY MATRIX (Authoritative Reference — use ONLY this)
════════════════════════════════════════════════════════════
{matrix_table}

════════════════════════════════════════════════════════════
MANDATORY GROUNDING RULES (prevent over-scoring)
════════════════════════════════════════════════════════════
1. If no patient was injured → clinical_score MUST be 1 or 2.
2. If no medical treatment was required → medical_score MUST be 1 or 2.
3. If the issue was found before reaching a patient (pre-market, QC,
   maintenance, inspection) → all scores MUST default to 1–3 range.
4. If the issue is a POTENTIAL risk but caused NO actual harm → scores
   reflect the ACTUAL current state, not the worst-case hypothetical.
5. Do NOT inflate scores. A crack found in maintenance with no patient
   impact is Score 1, NOT Score 7 or 8.
6. Match the matrix description WORD-FOR-WORD. If unsure, pick LOWER.

════════════════════════════════════════════════════════════
FEW-SHOT EXAMPLES
════════════════════════════════════════════════════════════
Example A — No patient harm, found in QC:
  Issue: "Battery crack found during routine QC. No patient exposure."
  → clinical_score: 1 (No injury)
  → reversibility_score: 1 (Fully reversible, no intervention)
  → medical_score: 1 (No medical intervention)
  → duration_score: 1 (No impact)

Example B — Patient experienced temporary discomfort:
  Issue: "Device caused slight skin irritation at injection site. Resolved in hours."
  → clinical_score: 2 (Minimal reversible discomfort)
  → reversibility_score: 2 (Fully reversible with minimal intervention)
  → medical_score: 2 (Self-care only)
  → duration_score: 2 (Minutes to hours)

Example C — Patient hospitalized, full recovery:
  Issue: "Infusion pump over-delivered dose. Patient hospitalized 2 days, full recovery."
  → clinical_score: 6 (Moderate temporary injury)
  → reversibility_score: 6 (Reversible with minor hospitalization)
  → medical_score: 6 (Minor hospitalization)
  → duration_score: 5 (1–3 days)

════════════════════════════════════════════════════════════
ISSUE TO EVALUATE
════════════════════════════════════════════════════════════
\"\"\"{issue}\"\"\"

════════════════════════════════════════════════════════════
TASK
════════════════════════════════════════════════════════════
Step 1 (internal reasoning — required):
  For each dimension, state which matrix level best matches the issue
  and WHY, citing the matrix description.

Step 2 (final output): Return ONLY this exact JSON — no markdown, no extra text:

{{
  "reasoning": {{
    "clinical":      "<which matrix level matches and why>",
    "reversibility": "<which matrix level matches and why>",
    "medical":       "<which matrix level matches and why>",
    "duration":      "<which matrix level matches and why>"
  }},
  "clinical_score": <integer 1-10>,
  "reversibility_score": <integer 1-10>,
  "medical_score": <integer 1-10>,
  "duration_score": <integer 1-10>
}}
"""
