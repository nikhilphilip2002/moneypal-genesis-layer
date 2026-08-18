"""Write a conversation checkpoint with the local LLM.

Everything here is best-effort. A failed or refused summarization leaves the record
untouched, and the transcript falls back to the token-budgeted recent window plus the
mechanically extracted session state — which is exact regardless. Compaction is an
optimization, never a correctness dependency.

Two safety properties matter and are asserted by tests:

* the call is always routed as ``sensitive=True``, so a checkpoint covering loan-book
  turns can never be sent to Groq (see ``workbench/models.py``);
* a response containing a tool call is rejected rather than stored as prose.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.services.workbench import models
from app.services.workbench.compaction import prompts, state as session_state

logger = logging.getLogger(__name__)

# A checkpoint should not swallow the very context it exists to protect.
TURN_TEXT_MAX_CHARS = 2000


class SummarizationError(RuntimeError):
    """The summarizer failed or returned something unusable."""


def _serialize(turns: list[dict[str, Any]], assistant_text_of) -> str:
    """Flatten turns to labelled text.

    Presented as data to read, not as a conversation to continue — the same trick pi
    uses. Long answers are clipped here because a checkpoint only needs the shape of an
    earlier turn, not its full body.
    """
    parts: list[str] = []
    for turn in turns:
        question = " ".join(str(turn.get("question", "")).split())
        if question:
            parts.append(f"[Analyst]: {question}")
        route = turn.get("route")
        if isinstance(route, dict) and route.get("sources"):
            parts.append(f"[Routed to]: {', '.join(str(s) for s in route['sources'])}")
        answer = assistant_text_of(turn)
        if answer:
            clipped = answer[:TURN_TEXT_MAX_CHARS]
            if len(answer) > TURN_TEXT_MAX_CHARS:
                clipped += f"\n[... {len(answer) - TURN_TEXT_MAX_CHARS} more characters truncated]"
            parts.append(f"[Console]: {clipped}")
    return "\n\n".join(parts)


async def write_checkpoint(
    turns_to_summarize: list[dict[str, Any]],
    *,
    assistant_text_of,
    previous_summary: str = "",
) -> str:
    """Summarize `turns_to_summarize`, folding into `previous_summary` when present."""
    if not turns_to_summarize:
        raise SummarizationError("nothing to summarize")

    conversation = _serialize(turns_to_summarize, assistant_text_of)
    if not conversation.strip():
        raise SummarizationError("turns produced no summarizable text")

    body = f"<conversation>\n{conversation}\n</conversation>\n\n"
    if previous_summary:
        body += f"<previous-checkpoint>\n{previous_summary}\n</previous-checkpoint>\n\n"
    body += prompts.UPDATE_PROMPT if previous_summary else prompts.INITIAL_PROMPT

    # Always sensitive: a checkpoint may describe loan-book results, so it must stay on
    # the local provider even when the deployment has opted into Groq for public sources.
    client = models.for_step("synthesize", sensitive=True)
    result = await client.complete(
        messages=[
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            {"role": "user", "content": body},
        ],
        max_tokens=settings.workbench_compaction_max_tokens,
        temperature=0.1,
    )
    text = (result.text or "").strip()
    if not text:
        raise SummarizationError("summarizer returned no text")
    if "<tool_call" in text or '"tool_calls"' in text:
        raise SummarizationError("summarizer attempted a tool call")
    return text


def build_payload(
    summary: str,
    *,
    first_kept_turn_id: str,
    state: session_state.SessionState,
    tokens_before: int,
) -> dict[str, Any]:
    return {
        "summary": summary,
        "first_kept_turn_id": first_kept_turn_id,
        "state": session_state.to_payload(state),
        "tokens_before": tokens_before,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
