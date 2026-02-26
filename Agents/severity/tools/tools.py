"""
tools.py

Utility functions supporting severity computation.

Responsibilities:
- Load and validate severity matrix configuration
- Apply weighted severity calculation
- Map numeric severity score to label
- Enforce matrix structural integrity
"""


import json
import os
from typing import Dict

# Loads severity matrix configuration from matrix.json
# Ensures required keys exist before returning data

# --------------------------------------------------
# Load Severity Matrix JSON
# --------------------------------------------------
def load_matrix() -> Dict:
    """
    Loads the severity matrix configuration from matrix.json
    """

    # Go one level up from tools directory
    base_path = os.path.dirname(os.path.dirname(__file__))
    file_path = os.path.join(base_path, "matrix.json")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"matrix.json not found at path: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    validate_matrix(data)
    return data

# Applies weighted formula using values defined in matrix.json
# Returns final rounded severity score (1–10)
# Prevents out-of-range values

# --------------------------------------------------
# Validate Matrix Structure
# --------------------------------------------------

def validate_matrix(data: Dict):
    required_keys = ["SEVERITY_LABELS", "WEIGHTS", "SEVERITY_MATRIX"]

    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing key in matrix.json: {key}")


# --------------------------------------------------
# Get Severity Label
# --------------------------------------------------

def get_severity_label(score: int, matrix_data: Dict) -> str:
    labels = matrix_data["SEVERITY_LABELS"]

    if str(score) not in labels:
        raise ValueError(f"Invalid severity score: {score}")

    return labels[str(score)]


def clamp_score(value: int) -> int:
    """Ensures score stays within 1–10."""
    return max(1, min(10, value))


# --------------------------------------------------
# Weighted Severity Calculation
# --------------------------------------------------

def calculate_weighted_severity(
    clinical_score: int,
    reversibility_score: int,
    medical_score: int,
    duration_score: int,
    matrix_data: Dict,
) -> int:
    """
    Applies weighted formula:

    0.4 * clinical
    + 0.2 * reversibility
    + 0.25 * medical
    + 0.15 * duration
    """

    weights = matrix_data["WEIGHTS"]

    weighted_score = (
        clinical_score * weights["clinical_score"]
        + reversibility_score * weights["reversibility_score"]
        + medical_score * weights["medical_score"]
        + duration_score * weights["duration_score"]
    )

    final_score = round(weighted_score)

    return clamp_score(final_score)
