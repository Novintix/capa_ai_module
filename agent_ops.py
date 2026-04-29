"""
AgentOps helpers and safe decorators.

This module keeps AgentOps optional and avoids runtime failures when the
SDK is not installed or the API key is missing.
"""

from contextlib import contextmanager
import json
import logging
import os
from typing import Any, Dict, List, Optional

_agentops_initialized = False


def init_agentops(default_tags: Optional[List[str]] = None) -> bool:
    """Initialize AgentOps once. Returns True if initialized."""
    global _agentops_initialized
    if _agentops_initialized:
        return True

    api_key = os.getenv("AGENTOPS_API_KEY")
    if not api_key:
        return False

    try:
        import agentops
    except Exception:
        return False

    kwargs: Dict[str, Any] = {
        "instrument_llm_calls": False,
        "log_level": "CRITICAL",
        "log_session_replay_url": False,
    }
    if default_tags:
        kwargs["default_tags"] = list(default_tags)

    logging.getLogger("agentops").setLevel(logging.WARNING)
    logging.getLogger("agentops").propagate = False

    try:
        agentops.init(api_key=api_key, **kwargs)
    except TypeError:
        if "default_tags" in kwargs:
            kwargs["tags"] = kwargs.pop("default_tags")
        for key in ["instrument_llm_calls", "log_level", "log_session_replay_url"]:
            kwargs.pop(key, None)
        agentops.init(api_key=api_key, **kwargs)

    _agentops_initialized = True
    return True


def _get_agentops():
    if not init_agentops():
        return None
    try:
        import agentops
        return agentops
    except Exception:
        return None


def _noop_decorator():
    def _wrapper(target):
        return target
    return _wrapper


def _safe_decorator_call(decorator_factory, name: Optional[str], attributes: Optional[Dict[str, Any]]):
    if name is None and attributes is None:
        return decorator_factory
    try:
        return decorator_factory(name=name, attributes=attributes)
    except TypeError:
        if name is not None:
            return decorator_factory(name=name)
        return decorator_factory


def agentops_agent(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    agentops = _get_agentops()
    if not agentops:
        return _noop_decorator()
    from agentops.sdk.decorators import agent as _agent
    return _safe_decorator_call(_agent, name, attributes)


def agentops_operation(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    agentops = _get_agentops()
    if not agentops:
        return _noop_decorator()
    from agentops.sdk.decorators import operation as _operation
    return _safe_decorator_call(_operation, name, attributes)


def agentops_workflow(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    agentops = _get_agentops()
    if not agentops:
        return _noop_decorator()
    from agentops.sdk.decorators import workflow as _workflow
    return _safe_decorator_call(_workflow, name, attributes)


def _get_tracer():
    if not init_agentops():
        return None
    try:
        from opentelemetry import trace
    except Exception:
        return None
    return trace.get_tracer("capa_ai_module.agentops")


def _set_span_attributes(span, attributes: Optional[Dict[str, Any]] = None) -> None:
    if span is None or not attributes:
        return
    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            try:
                value = json.dumps(value, ensure_ascii=True)
            except Exception:
                value = str(value)
        span.set_attribute(key, value)


@contextmanager
def llm_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Create a best-effort LLM span linked to AgentOps tracing."""
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as span:
        _set_span_attributes(span, attributes)
        yield span
