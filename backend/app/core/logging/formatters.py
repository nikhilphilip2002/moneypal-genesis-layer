from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

from app.core.logging.context import get_trace_context

# Sensitive key names to redact in dictionary payloads
_SENSITIVE_KEYS = frozenset({
    "authorization",
    "api_key",
    "groq_api_key",
    "groq_api_key_secondary",
    "qdrant_api_key",
    "secret",
    "password",
    "token",
})

_BEARER_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE)
_PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_PHONE_REGEX = re.compile(r"\b(?:\+91|91)?[6-9]\d{9}\b")


def redact_sensitive_data(obj: Any, *, mask_pii: bool = False) -> Any:
    """Recursively redact secrets and optionally mask common Indian PII in log structures."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_KEYS:
                cleaned[k] = "***REDACTED***"
            else:
                cleaned[k] = redact_sensitive_data(v, mask_pii=mask_pii)
        return cleaned
    if isinstance(obj, (list, tuple)):
        return [redact_sensitive_data(item, mask_pii=mask_pii) for item in obj]
    if isinstance(obj, str):
        val = _BEARER_REGEX.sub(r"\1***REDACTED***", obj)
        if mask_pii:
            val = _PAN_REGEX.sub(r"***PAN***", val)
            val = _PHONE_REGEX.sub(r"***PHONE***", val)
        return val
    return obj


class JSONLinesFormatter(logging.Formatter):
    """Format LogRecord instances as single-line JSON with context correlation."""

    def __init__(self, *, mask_pii: bool = False) -> None:
        super().__init__()
        self.mask_pii = mask_pii

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_trace_context()

        # Base fields
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ctx.get("trace_id", "")),
            "conversation_id": getattr(record, "conversation_id", ctx.get("conversation_id", "")),
            "turn_id": getattr(record, "turn_id", ctx.get("turn_id", "")),
            "user": getattr(record, "user", getattr(record, "username", ctx.get("username", ""))),
            "role": getattr(record, "role", ctx.get("role", "")),
        }

        # Structured extra payload passed via extra={...}
        # Filter standard logging attributes to avoid pollution
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "trace_id", "conversation_id",
            "turn_id", "user", "username", "role",
        }
        for k, v in record.__dict__.items():
            if k not in standard_attrs and not k.startswith("_"):
                if k == "payload" and isinstance(v, dict):
                    entry.update(v)
                else:
                    entry[k] = v

        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        elif record.exc_text:
            entry["exc"] = record.exc_text

        sanitized = redact_sensitive_data(entry, mask_pii=self.mask_pii)
        return json.dumps(sanitized, default=str, separators=(",", ":"))
