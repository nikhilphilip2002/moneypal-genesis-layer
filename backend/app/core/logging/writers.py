from __future__ import annotations

import logging
from typing import Any

from app.core.logging.context import get_trace_context
from app.core.logging.setup import (
    get_event_logger,
    get_parsed_llm_logger,
    get_raw_llm_logger,
)


def _inject_trace_context(payload: dict[str, Any]) -> dict[str, Any]:
    ctx = get_trace_context()
    for k in ("trace_id", "conversation_id", "turn_id", "user", "username", "role"):
        if k in ctx and k not in payload:
            payload[k] = ctx[k]
    return payload


def log_raw_trace(
    message: str,
    *,
    event: str = "llm_trace",
    provider: str = "",
    model: str = "",
    prompt: Any = None,
    completion: Any = None,
    raw_payload: Any = None,
    raw_response: Any = None,
    duration_ms: float = 0.0,
    usage: dict[str, Any] | None = None,
    status_code: int = 200,
    level: int = logging.INFO,
    **extra: Any,
) -> None:
    """Write a raw LLM request/response trace to the rotating raw trace stream."""
    logger = get_raw_llm_logger()
    payload = _inject_trace_context({
        "event": event,
        "provider": provider,
        "model": model,
        "duration_ms": round(duration_ms, 2),
        "status_code": status_code,
        **extra,
    })
    if prompt is not None:
        payload["prompt"] = prompt
    if completion is not None:
        payload["completion"] = completion
    if raw_payload is not None:
        payload["raw_payload"] = raw_payload
    if raw_response is not None:
        payload["raw_response"] = raw_response
    if usage is not None:
        payload["usage"] = usage

    logger.log(level, message, extra={"payload": payload})


def log_parsed_output(
    message: str,
    *,
    event: str = "llm_parsed",
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    tool_result: Any = None,
    schema_name: str | None = None,
    parsed: Any = None,
    status: str = "success",
    error: str | None = None,
    duration_ms: float = 0.0,
    level: int = logging.INFO,
    **extra: Any,
) -> None:
    """Write a parsed LLM output or tool call record to the rotating parsed stream."""
    logger = get_parsed_llm_logger()
    payload = _inject_trace_context({
        "event": event,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        **extra,
    })
    if tool_name is not None:
        payload["tool_name"] = tool_name
    if tool_args is not None:
        payload["tool_args"] = tool_args
    if tool_result is not None:
        payload["tool_result"] = tool_result
    if schema_name is not None:
        payload["schema_name"] = schema_name
    if parsed is not None:
        payload["parsed"] = parsed
    if error is not None:
        payload["error"] = error

    logger.log(level, message, extra={"payload": payload})


def log_app_event(
    message: str,
    *,
    event: str = "app_event",
    stage: str | None = None,
    outcome: str | None = None,
    duration_ms: float = 0.0,
    data: dict[str, Any] | None = None,
    level: int = logging.INFO,
    **extra: Any,
) -> None:
    """Write an application domain event to the rotating application events stream."""
    logger = get_event_logger()
    payload = _inject_trace_context({
        "event": event,
        "duration_ms": round(duration_ms, 2),
        **extra,
    })
    if stage is not None:
        payload["stage"] = stage
    if outcome is not None:
        payload["outcome"] = outcome
    if data is not None:
        payload["data"] = data

    logger.log(level, message, extra={"payload": payload})
