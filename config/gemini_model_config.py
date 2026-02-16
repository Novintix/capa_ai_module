"""
Gemini Model Configuration
Centralized configuration for LLM models and parameters.
"""

# Google Gemini Configuration
MODEL_NAME = "gemini-2.0-flash"
TEMPERATURE = 0.0
MAX_TOKENS = 2000
TIMEOUT = 60

# Scoring Configuration
MIN_SCORE = 1
MAX_SCORE = 10
DEFAULT_SCORE_ON_ERROR = 10

# Confidence Thresholds
HIGH_CONFIDENCE = 0.9
MEDIUM_CONFIDENCE = 0.7
LOW_CONFIDENCE = 0.5
