# orchestrator_service/utils.py

import datetime


def to_serializable(obj):
    """
    Recursively converts any object to a JSON-serializable form.
    Handles: datetime, Pydantic models (v1 + v2), dicts, lists, primitives.
    Apply to every agent result before writing to state.
    """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):          # Pydantic v2
        return to_serializable(obj.model_dump())
    if hasattr(obj, "dict"):                # Pydantic v1
        return to_serializable(obj.dict())
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    return obj