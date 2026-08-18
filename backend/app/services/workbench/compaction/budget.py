"""Token accounting for the workbench transcript.

The rule, borrowed from the pi coding agent: trust the provider where it has spoken,
estimate only what came after. A turn that has run carries the prompt size the model
actually saw; turns added since are estimated with a deliberately conservative
characters/4 heuristic, so the number errs high and we compact slightly early rather
than overrunning the window.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.config import settings

# Conservative: real tokenizers average better than 4 chars/token on English prose, so
# dividing by 4 overestimates. Overestimating is the safe direction here.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def turn_tokens(turn: dict[str, Any], assistant_text: str) -> int:
    """Estimated cost of one turn as it appears in a transcript."""
    return estimate_tokens(str(turn.get("question", ""))) + estimate_tokens(assistant_text)


def measured_prompt_tokens(turn: dict[str, Any]) -> int | None:
    """The provider's own prompt size for this turn, when it recorded one."""
    usage = turn.get("usage")
    if not isinstance(usage, dict):
        return None
    tokens = usage.get("prompt_tokens")
    if not isinstance(tokens, int) or tokens <= 0:
        return None
    return tokens


def transcript_tokens(turns: list[dict[str, Any]], assistant_text_of) -> int:
    """Estimate what the next call's transcript will cost.

    Walks back to the most recent turn with measured usage, takes it as ground truth,
    and estimates only the turns after it. Falls back to estimating everything when no
    turn has usage yet (an older conversation, or one whose synthesis step failed).
    """
    last_measured_index = -1
    measured = 0
    for index in range(len(turns) - 1, -1, -1):
        tokens = measured_prompt_tokens(turns[index])
        if tokens is not None:
            last_measured_index = index
            measured = tokens
            break

    if last_measured_index < 0:
        return sum(turn_tokens(turn, assistant_text_of(turn)) for turn in turns)

    # `prompt_tokens` for turn N covers the transcript as it stood at the *start* of that
    # turn plus the question — the answer was the completion, not part of the prompt. The
    # next transcript will contain that answer, so it has to be added back explicitly or
    # every estimate is short by one assistant message.
    measured_answer = estimate_tokens(assistant_text_of(turns[last_measured_index]))
    trailing = sum(
        turn_tokens(turn, assistant_text_of(turn))
        for turn in turns[last_measured_index + 1 :]
    )
    return measured + measured_answer + trailing


def budget_tokens() -> int:
    """How much of the context window the transcript may occupy."""
    return max(0, settings.workbench_context_window - settings.workbench_reserve_tokens)


# The compressed layers (checkpoint summary + session state) precede every live turn, so
# they get a bounded share of the budget rather than an open claim on it. Half leaves
# room for at least one substantial turn.
COMPRESSED_SHARE = 0.5
SUMMARY_SHARE = 0.25


def clip_to_tokens(text: str, max_tokens: int) -> str:
    """Clip text to an approximate token count, marking what was removed.

    Used only as a last resort — on the compressed layers and on a single turn so large
    it would otherwise consume the whole window on its own.
    """
    if max_tokens <= 0:
        return ""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    removed = len(text) - max_chars
    return f"{text[:max_chars]}\n[... {removed} characters truncated to fit the context window]"


def should_compact(turns: list[dict[str, Any]], assistant_text_of) -> bool:
    """Whether this conversation has outgrown its share of the context window."""
    if not settings.workbench_compaction_enabled:
        return False
    return transcript_tokens(turns, assistant_text_of) > budget_tokens()
