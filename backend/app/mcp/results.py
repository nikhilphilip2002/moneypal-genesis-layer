"""Minimal result envelope for Moneypal-owned MCP tools."""

from __future__ import annotations

from typing import Any


class OwnedToolResultError(RuntimeError):
    """An owned MCP tool returned a malformed or unsuccessful result."""

    code = "MCP_TOOL_ERROR"
    retryable = True

    def __init__(self, message: str):
        super().__init__(message)
        self.details: dict[str, Any] = {}


def success(data: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "data": data}


def failure(
    code: str,
    message: str,
    *,
    retryable: bool,
    **details: Any,
) -> dict[str, Any]:
    error = {
        "code": code,
        "message": message,
        "retryable": retryable,
        **details,
    }
    return {"success": False, "error": error}


def require_owned_data(result: Any, *, tool_name: str) -> dict[str, Any]:
    """Extract the object payload from FastMCP's native parsed result."""
    envelope = result.data
    if not isinstance(envelope, dict) or not isinstance(
        envelope.get("success"), bool
    ):
        raise OwnedToolResultError(
            f"MCP tool {tool_name!r} returned an invalid result envelope"
        )
    if envelope["success"]:
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise OwnedToolResultError(
                f"MCP tool {tool_name!r} returned no structured object"
            )
        return data

    error_payload = envelope.get("error")
    if not isinstance(error_payload, dict):
        raise OwnedToolResultError(
            f"MCP tool {tool_name!r} returned an invalid error envelope"
        )
    error = OwnedToolResultError(
        str(error_payload.get("message") or f"MCP tool {tool_name!r} failed")[
            :1500
        ]
    )
    error.code = str(error_payload.get("code") or "MCP_TOOL_ERROR")
    error.retryable = bool(error_payload.get("retryable", True))
    error.details = dict(error_payload)
    raise error


__all__ = [
    "OwnedToolResultError",
    "failure",
    "require_owned_data",
    "success",
]
