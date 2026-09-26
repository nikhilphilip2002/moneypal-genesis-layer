"""Request accounting for the server's Messages token-count endpoint."""

from __future__ import annotations

import json
import math
from typing import Any

from app.services.nlq.llm.messages import ChatMessage


def estimate_request_tokens(
    messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None
) -> int:
    return math.ceil(
        len(
            json.dumps(
                {"messages": messages, "tools": tools or []},
                ensure_ascii=False,
            )
        )
        / 3
    )


def counting_payload(
    model: str, messages: list[ChatMessage], tools: list[dict[str, Any]] | None
) -> dict[str, Any]:
    system: list[dict[str, Any]] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        content = message.get("content")
        blocks = (
            [{"type": "text", "text": content}]
            if isinstance(content, str) and content
            else [
                {"type": "text", "text": block["text"]}
                for block in content
                if block.get("type") == "text"
            ]
            if isinstance(content, list)
            else []
        )
        if isinstance(content, list) and any(
            block.get("type") != "text" for block in content
        ):
            raise ValueError("unsupported content for Messages token counting")
        if role in {"system", "developer"}:
            system.extend(blocks)
            continue
        if role == "tool":
            blocks = [
                {
                    "type": "tool_result",
                    "tool_use_id": message["tool_call_id"],
                    "content": blocks,
                }
            ]
            role = "user"
        for call in message.get("tool_calls") or []:
            function = call["function"]
            blocks.append(
                {
                    "type": "tool_use",
                    "id": call["id"],
                    "name": function["name"],
                    "input": json.loads(function["arguments"]),
                }
            )
        if converted and converted[-1]["role"] == role:
            converted[-1]["content"].extend(blocks)
        else:
            converted.append({"role": role, "content": blocks})
    payload: dict[str, Any] = {"model": model, "messages": converted}
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = [
            {
                "name": tool["function"]["name"],
                "description": tool["function"].get("description", ""),
                "input_schema": tool["function"]["parameters"],
            }
            for tool in tools
        ]
    return payload


def is_context_overflow(error: object) -> bool:
    text = f"{error} {getattr(error, 'body', '')}".lower()
    return any(
        marker in text
        for marker in (
            "context window",
            "context length",
            "context_length",
            "context size",
            "n_ctx",
            "too many tokens",
            "exceeds the available",
            "maximum context",
            "prompt is too long",
        )
    )
