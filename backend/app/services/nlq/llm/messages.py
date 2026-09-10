"""Canonical chat-message assembly.

Some OpenAI-compatible chat templates only honour the first system message.  Keep every
system instruction, but combine them into one leading message so checkpoints and session
state cannot be silently dropped by a provider-specific template.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, NotRequired, Required, TypedDict


class PromptCacheBreakpoint(TypedDict):
    mode: Literal["explicit"]


class ContentPartText(TypedDict):
    type: Literal["text"]
    text: str
    prompt_cache_breakpoint: NotRequired[PromptCacheBreakpoint]


class SystemMessage(TypedDict):
    role: Literal["system"]
    content: str | list[ContentPartText]


class ChatMessage(TypedDict, total=False):
    """OpenAI-compatible message shape used by both legacy and native-tool calls.

    ``content`` is nullable for an assistant message containing native tool calls. Tool
    results carry ``tool_call_id`` and assistant messages preserve the provider's native
    ``tool_calls`` array for replay on the next model round.
    """

    role: Required[Literal["system", "user", "assistant", "tool"]]
    content: NotRequired[str | list[ContentPartText] | None]
    name: NotRequired[str]
    tool_call_id: NotRequired[str]
    tool_calls: NotRequired[list[dict[str, Any]]]
    reasoning_content: NotRequired[str]


def coalesce_system_messages(
    messages: Iterable[ChatMessage],
) -> list[ChatMessage]:
    """Return a fresh message list with at most one, leading, system message.

    System fragments retain their original relative order.  User and assistant messages
    also retain their order; only system fragments are lifted into the leading message.
    """
    system_groups: list[list[ContentPartText]] = []
    has_structured_content = False
    conversation: list[ChatMessage] = []
    for message in messages:
        copied: ChatMessage = dict(message)
        if copied.get("role") == "system":
            content = copied.get("content") or ""
            if isinstance(content, str) and content.strip():
                system_groups.append([{"type": "text", "text": content}])
            elif isinstance(content, list):
                parts = [dict(part) for part in content if part.get("text", "").strip()]
                if parts:
                    system_groups.append(parts)
                    has_structured_content = True
        else:
            conversation.append(copied)

    if not system_groups:
        return conversation
    if has_structured_content:
        merged: list[ContentPartText] = []
        for group in system_groups:
            if merged:
                merged.append({"type": "text", "text": "\n\n"})
            merged.extend(group)
        return [
            {"role": "system", "content": merged},
            *conversation,
        ]
    return [
        {
            "role": "system",
            "content": "\n\n".join(group[0]["text"] for group in system_groups),
        },
        *conversation,
    ]


__all__ = [
    "ChatMessage",
    "ContentPartText",
    "PromptCacheBreakpoint",
    "SystemMessage",
    "coalesce_system_messages",
]
