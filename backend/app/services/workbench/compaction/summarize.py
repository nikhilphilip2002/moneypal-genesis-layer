"""Write a conversation checkpoint with the local LLM.

Everything here is best-effort. A failed or refused summarization leaves the record
untouched, and the transcript falls back to the token-budgeted recent window plus the
mechanically extracted session state — which is exact regardless. Compaction is an
optimization, never a correctness dependency.

Two safety properties matter and are asserted by tests:

* the call is always routed as ``sensitive=True``, so a checkpoint covering loan-book
  turns use the same deployment-controlled model endpoint as every other step;
* a response containing a tool call is rejected rather than stored as prose.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.services.workbench import models
from app.services.workbench.compaction import state as session_state

SYSTEM_PROMPT = (
    "You are a context summarization assistant for a banking intelligence console. "
    "Read the conversation and produce a structured checkpoint another model will use "
    "to continue it.\n"
    "Do NOT continue the conversation. Do NOT answer any question that appears in it. "
    "Output only the checkpoint."
)

_FORMAT = """## Line of Enquiry
[What is the analyst investigating? One or two sentences. Multiple items if the conversation covered several.]

## Resolved Context
- [Bindings a follow-up question depends on: which institution, which period, which product or branch filter, which document is pinned]
- [Or "(none)" if nothing has been pinned down]

## Open Threads
- [Questions raised but not yet answered, and comparisons the analyst asked for that are incomplete]
- [Or "(none)"]

## Caveats & Refusals
- [Anything that was refused, unavailable, or came with a stated confidence limit]
- [Or "(none)"]

## Notes
- [Anything else needed to continue that does not fit above]
- [Or "(none)"]"""

_RULES = """
Rules:
- Do NOT restate numeric figures. They are carried separately and exactly; repeating them here risks corrupting them.
- Refer to figures by subject instead ("MSME credit outstanding was established for FY25").
- Preserve exact institution names, metric names, product names and period labels.
- Keep every section short. This is a checkpoint, not a report."""

INITIAL_PROMPT = f"""The messages above are a conversation to summarize. Create a structured checkpoint.

Use this EXACT format:

{_FORMAT}
{_RULES}"""

UPDATE_PROMPT = f"""The messages above are NEW turns to fold into the existing checkpoint given in <previous-checkpoint> tags.

RULES:
- PRESERVE everything from the previous checkpoint that is still true
- ADD what the new turns established
- MOVE items out of "Open Threads" once they have been answered
- REMOVE items that are no longer relevant
- Keep exact institution, metric, product and period names

Use this EXACT format:

{_FORMAT}
{_RULES}"""

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
    body += UPDATE_PROMPT if previous_summary else INITIAL_PROMPT

    # Always sensitive: a checkpoint may describe loan-book results, so it must stay on
    client = models.client()
    result = await client.complete(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": body},
        ],
        call_purpose="compaction",
        prompt_version="workbench-compaction-v1",
        max_output_tokens=settings.workbench_compaction_max_tokens,
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
