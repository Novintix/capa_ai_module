"""
__init__.py

CAPA Effectiveness Evaluation Agent package.

Removed: EffectivenessEvaluationRequest
  - No longer needed since endpoint switched to multipart/form-data.
  - Each field is now a direct Form() parameter in router.py.
"""

from .model import (
    ActionItemInput,
    EffectivenessEvaluationInput,
    EvaluatedAction,
    EffectivenessEvaluationResponse,
)
from .router import router