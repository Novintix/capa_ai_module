"""
AgentOps helpers and safe decorators.

This module keeps AgentOps optional and avoids runtime failures when the
SDK is not installed or the API key is missing.
"""

from contextlib import contextmanager
import functools
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

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
        "auto_start_session":     False,       # prevent phantom "Default" trace on init
        "instrument_llm_calls":   False,       # Disables noisy LangGraph .task and Bedrock embeddings spans
        "log_level":              "CRITICAL",
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
        for key in ["log_level", "log_session_replay_url"]:
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


def _clear_otel_span_context():
    """
    Detach the currently active OpenTelemetry span from the context so that
    the next ao.start_trace() call always produces a true root trace rather
    than a child span nested inside a previous trace.

    Returns an opaque token that must be passed to _restore_otel_context()
    once the new trace ends, to avoid context leakage in the other direction.
    """
    try:
        from opentelemetry import context as _otel_ctx
        # Attaching an empty Context detaches any inherited parent span.
        token = _otel_ctx.attach(_otel_ctx.Context())
        return token
    except Exception:
        return None


def _restore_otel_context(token) -> None:
    """Undo the context detachment created by _clear_otel_span_context()."""
    if token is None:
        return
    try:
        from opentelemetry import context as _otel_ctx
        _otel_ctx.detach(token)
    except Exception:
        pass


def agentops_session(
    name: str = "agent_run",
    tags: Optional[List[str]] = None,
):
    """
    Decorator that creates a single AgentOps trace per call with the given
    name and tags. Replaces the phantom "Default" trace produced by
    agentops.init(auto_start_session=True).

    Usage:
        @agentops_session(name="risk_analysis", tags=["capa_ai_module"])
        async def analyze(request: CAPARequest): ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            ao = _get_agentops()
            if ao is None:
                return await fn(*args, **kwargs)
            # Detach any inherited OTel span so start_trace() creates a true
            # root trace, not a child of whatever ran before this request.
            otel_token = _clear_otel_span_context()
            trace = None
            try:
                trace = ao.start_trace(trace_name=name, tags=tags or [])
                result = await fn(*args, **kwargs)
                ao.end_trace(trace, end_state="Success")
                return result
            except Exception:
                if trace is not None:
                    try:
                        ao.end_trace(trace, end_state="Error")
                    except Exception:
                        pass
                raise
            finally:
                _restore_otel_context(otel_token)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            ao = _get_agentops()
            if ao is None:
                return fn(*args, **kwargs)
            # Same isolation as async_wrapper — prevents Why Analysis /
            # Risk Analysis OTel context from bleeding into subsequent traces.
            otel_token = _clear_otel_span_context()
            trace = None
            try:
                trace = ao.start_trace(trace_name=name, tags=tags or [])
                result = fn(*args, **kwargs)
                ao.end_trace(trace, end_state="Success")
                return result
            except Exception:
                if trace is not None:
                    try:
                        ao.end_trace(trace, end_state="Error")
                    except Exception:
                        pass
                raise
            finally:
                _restore_otel_context(otel_token)

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator


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
