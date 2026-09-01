"""Canonical chat-message assembly.

Some OpenAI-compatible chat templates only honour the first system message.  Keep every
system instruction, but combine them into one leading message so checkpoints and session
state cannot be silently dropped by a provider-specific template.
"""

from __future__ import annotations

from collections.abc import Iterable


def coalesce_system_messages(
    messages: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    """Return a fresh message list with at most one, leading, system message.

    System fragments retain their original relative order.  User and assistant messages
    also retain their order; only system fragments are lifted into the leading message.
    """
    system_parts: list[str] = []
    conversation: list[dict[str, str]] = []
    for message in messages:
        copied = dict(message)
        if copied.get("role") == "system":
            content = copied.get("content", "")
            if content.strip():
                system_parts.append(content)
        else:
            conversation.append(copied)

    if not system_parts:
        return conversation
    return [
        {"role": "system", "content": "\n\n".join(system_parts)},
        *conversation,
    ]
