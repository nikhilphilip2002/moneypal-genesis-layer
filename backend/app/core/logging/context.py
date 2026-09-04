from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator
import uuid

_current_trace: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "moneypal_trace_context",
    default={},
)


def get_trace_context() -> dict[str, Any]:
    """Return a copy of the current thread/task trace context."""
    return dict(_current_trace.get())


def set_trace_context(
    *,
    trace_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    username: str | None = None,
    role: str | None = None,
    **kwargs: Any,
) -> contextvars.Token:
    """Update trace context variables, returning a Token to restore previous state."""
    current = dict(_current_trace.get())
    if trace_id is not None:
        current["trace_id"] = trace_id
    elif "trace_id" not in current:
        current["trace_id"] = uuid.uuid4().hex

    if conversation_id is not None:
        current["conversation_id"] = conversation_id
    if turn_id is not None:
        current["turn_id"] = turn_id
    if username is not None:
        current["username"] = username
    if role is not None:
        current["role"] = role
    for k, v in kwargs.items():
        if v is not None:
            current[k] = v

    return _current_trace.set(current)


@contextmanager
def bind_trace(
    *,
    trace_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    username: str | None = None,
    role: str | None = None,
    **kwargs: Any,
) -> Iterator[dict[str, Any]]:
    """Context manager scoping trace variables to a block/coroutine."""
    token = set_trace_context(
        trace_id=trace_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        username=username,
        role=role,
        **kwargs,
    )
    try:
        yield get_trace_context()
    finally:
        _current_trace.reset(token)
