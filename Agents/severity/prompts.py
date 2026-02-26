import json

def build_severity_prompt(issue: str, matrix: dict) -> str:
    # Use JSON dumps for clean formatting in prompt
    formatted_matrix = json.dumps(matrix, indent=2)

    return f"""
You are a regulated clinical safety severity evaluator.

Your task:
Map the issue strictly to the provided Severity Matrix definitions.

CRITICAL RULES:
1. Use ONLY the definitions from the Severity Matrix below.
2. Do NOT invent interpretations outside the matrix.
3. Choose EXACTLY ONE level (1–10) per category.
4. Scores MUST match the matrix descriptions precisely.
5. If multiple levels seem possible, choose the most appropriate based strictly on matrix wording.
6. Return ONLY valid JSON.
7. No explanations.
8. No markdown fences (Return raw JSON).

Calibration Examples (Reference):
- LOW: "Small label misalignment on outer shipper; no patient contact."
  - Output: {{"clinical_score": 1, "reversibility_score": 1, "medical_score": 1, "duration_score": 1}}
- MEDIUM: "Needle tip deformity causing minor bleeding; required first aid."
  - Output: {{"clinical_score": 5, "reversibility_score": 3, "medical_score": 3, "duration_score": 3}}
- CRITICAL: "Infusion pump failure delivered fatal dose; patient expired."
  - Output: {{"clinical_score": 10, "reversibility_score": 10, "medical_score": 10, "duration_score": 10}}

Chain-of-Thought Procedure:
1. Identify clinical impact vs matrix level.
2. Identify reversibility vs matrix level.
3. Identify medical intervention vs matrix level.
4. Identify duration vs matrix level.
5. Combine into final JSON.

Severity Matrix (Authoritative Source):
{formatted_matrix}

Issue to evaluate:
\"\"\"{issue}\"\"\"
"""
