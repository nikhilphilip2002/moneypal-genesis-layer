"""Conversation compaction for the workbench.

Layered so that each layer is useful without the one above it:

* ``budget``   — token accounting from real provider usage (no LLM)
* ``state``    — figures, sources, refusals extracted from turns (no LLM)
* ``summarize``— the prose checkpoint (one LLM call, best effort)

The checkpoint is a pointer plus a summary, never a deletion: ``first_kept_turn_id``
marks where verbatim replay resumes, and every turn stays in the record. Dropping the
checkpoint costs context and nothing else, which is what makes it safe to write
automatically.
"""

from __future__ import annotations

import logging

from app.core.config import settings

from . import budget, prompts, state, summarize

logger = logging.getLogger(__name__)

__all__ = ["budget", "prompts", "state", "summarize", "maybe_compact", "compact_now"]


async def maybe_compact(conversation_id: str, user: str) -> bool:
    """Checkpoint the conversation if it has outgrown the budget. Never raises.

    Called after a turn completes, while the user is reading the answer, so the cost
    never lands on the critical path of a question.

    The token budget is the trigger, not the turn count. Turn count alone would fire a
    summarization call after every turn past the keep-window even for a conversation of a
    few hundred tokens — paying for a checkpoint nobody needs.
    """
    if not settings.workbench_compaction_enabled:
        return False
    try:
        from app.services.workbench import history

        record = history.get(conversation_id, user=user)
        if record is None:
            return False
        # Measure the replay the agent will be sent: the live turns after any checkpoint,
        # as `build_native_transcript` shapes them, plus the checkpoint itself.
        measure = history.measure_native_replay(record)
        limit = budget.budget_tokens()
        if measure.newest_turn_tokens > limit:
            # Summarizing older turns cannot shrink the newest one. Leave the record as
            # it is; the next transcript load reports `single_turn_exceeds_budget`.
            logger.warning(
                "workbench compaction cannot help %s: newest turn replays at %d tokens "
                "against a budget of %d (single_turn_exceeds_budget)",
                conversation_id, measure.newest_turn_tokens, limit,
            )
            return False
        if measure.tokens <= limit:
            return False
        return await compact_now(conversation_id, user)
    except Exception:  # noqa: BLE001 - compaction is an optimization, not a dependency
        logger.exception("workbench compaction failed for %s", conversation_id)
        return False


async def compact_now(conversation_id: str, user: str) -> bool:
    """Force a checkpoint regardless of the threshold. Returns whether one was written."""
    from app.services.workbench import history

    record = history.get(conversation_id, user=user)
    if record is None:
        return False

    complete = [turn for turn in record.turns if turn.get("status") != "running"]
    keep = max(1, settings.workbench_keep_recent_turns)
    if len(complete) <= keep:
        return False

    previous = record.compaction if isinstance(record.compaction, dict) else None
    previous_summary = str(previous.get("summary", "")) if previous else ""
    previous_first_kept = str(previous.get("first_kept_turn_id", "")) if previous else ""

    to_summarize = complete[:-keep]
    first_kept_turn_id = str(complete[-keep].get("id", ""))
    if not first_kept_turn_id:
        return False
    if previous_first_kept == first_kept_turn_id:
        # Nothing new has aged out since the last checkpoint.
        return False

    # Only the turns that aged out *since* the previous checkpoint need summarizing; the
    # rest is already represented in previous_summary. This keeps cost flat as the
    # conversation grows, rather than re-reading the whole history each time.
    if previous_first_kept:
        for index, turn in enumerate(to_summarize):
            if turn.get("id") == previous_first_kept:
                to_summarize = to_summarize[index:]
                break
    if not to_summarize:
        return False

    tokens_before = history.measure_native_replay(record).tokens
    summary = await summarize.write_checkpoint(
        to_summarize,
        assistant_text_of=history.assistant_text,
        previous_summary=previous_summary,
    )
    # The pointer on the record is what replay consults; the summary is also appended
    # as an event naming every turn it replaces. Nothing is deleted.
    history.set_compaction(
        conversation_id,
        user,
        summarize.build_payload(
            summary,
            first_kept_turn_id=first_kept_turn_id,
            state=state.from_turns(complete, history.assistant_text),
            tokens_before=tokens_before,
        ),
        replaced_turn_ids=[str(turn.get("id", "")) for turn in to_summarize],
    )
    logger.info(
        "workbench compaction: %s summarized %d turn(s), tokens_before=%d",
        conversation_id, len(to_summarize), tokens_before,
    )
    return True
