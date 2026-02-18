"""
Occurrence Agent Prompts

Builds the scoring prompt dynamically from a metrics definition dict.
The metrics dict can be loaded from metrics.json, an uploaded Excel, PDF, etc.
"""

import json
import os

# Default metrics file path
DEFAULT_METRICS_PATH = os.path.join(os.path.dirname(__file__), "metrics.json")


def load_metrics(metrics_path: str = None) -> dict:
    """Load metrics from a JSON file. Falls back to default metrics.json."""
    path = metrics_path or DEFAULT_METRICS_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(description: str, product: str, date: str,
                 similar_cases: str, context: str,
                 metrics: dict = None) -> str:
    """
    Build the full scoring prompt dynamically from the metrics definition.
    If metrics is None, loads from the default metrics.json.
    """
    if metrics is None:
        metrics = load_metrics()

    parameters = metrics.get("parameters", {})

    # Build per-parameter scoring guide
    param_guide = ""
    weights_block = "| Code | Parameter | Weight |\n|------|-----------|--------|\n"

    for code, param in parameters.items():
        name = param["name"]
        weight = param["weight"]
        levels = param["levels"]

        param_guide += f"\n#### {code} — {name} (Weight: {int(weight * 100)}%)\n"
        for score, desc in sorted(levels.items(), key=lambda x: int(x[0])):
            param_guide += f"{score} → {desc}\n"

        weights_block += f"| {code} | {name} | {int(weight * 100)}% |\n"

    prompt = f"""
You are a Quality Assurance Expert specializing in CAPA (Corrective and Preventive Action) Risk Assessment.
Analyze the input and assign a score (1-10) for each of the 10 parameters below.

### INPUT DATA
- **Complaint Description**: {description}
- **Product**: {product}
- **Date**: {date}
- **Similar Historical Cases**: {similar_cases}
- **Additional Context**: {context}

---

### PARAMETER SCORING GUIDE
For each parameter, pick the score (1-10) whose description best matches the input.
{param_guide}
---

### PARAMETER WEIGHTS
{weights_block}
---

### INSTRUCTIONS
- Match the input data to the closest description for each parameter.
- Return ONLY a valid JSON object. No extra text, no markdown.

### OUTPUT FORMAT
{{
  "HF": <integer 1-10>,
  "TR": <integer 1-10>,
  "PS": <integer 1-10>,
  "PC": <integer 1-10>,
  "DM": <integer 1-10>,
  "SY": <integer 1-10>,
  "OE": <integer 1-10>,
  "CA": <integer 1-10>,
  "SU": <integer 1-10>,
  "AU": <integer 1-10>,
  "reasoning": "<brief explanation>"
}}
"""
    return prompt


def get_weights(metrics: dict = None) -> dict:
    """Extract weights dict from metrics definition."""
    if metrics is None:
        metrics = load_metrics()
    return {
        code: param["weight"]
        for code, param in metrics.get("parameters", {}).items()
    }


# Keep WEIGHTS as a module-level constant for backward compatibility
WEIGHTS = get_weights()
