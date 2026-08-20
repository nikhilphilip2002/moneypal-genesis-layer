"""Durable, user-owned Workbench conversations.

The saved record serves two different consumers without conflating them:

* the UI receives the complete renderable turns, including cards;
* the LLM receives a bounded text transcript derived from those turns.

Raw chart JSON, SQL, lineage, and tool logs are never copied into the model transcript.
They remain in the durable UI record while compact human-readable values and summaries are
used as assistant messages.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

TABLE = "public.workbench_conversations"
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    conversation_id text PRIMARY KEY,
    owner_username  text NOT NULL DEFAULT 'legacy',
    title           text NOT NULL,
    record_version  integer NOT NULL DEFAULT 2,
    record_json     jsonb NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
"""
MIGRATIONS = (
    f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS owner_username text NOT NULL DEFAULT 'legacy'",
    f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS record_version integer NOT NULL DEFAULT 2",
)

TITLE_MAX = 80
# v3 adds `compaction` (checkpoint summary + mechanically extracted session state) and
# per-turn `usage`. v2 records load with compaction=None and behave exactly as before.
RECORD_VERSION = 3
OLDER_TURN_MAX_CHARS = 900
CARD_ROWS_IN_CONTEXT = 20
_table_ready = False


@dataclass(slots=True)
class ConversationRecord:
    conversation_id: str
    title: str
    updated_at: datetime
    turns: list[dict[str, Any]] = field(default_factory=list)
    owner_username: str = "anonymous"
    record_version: int = RECORD_VERSION
    # Checkpoint written by the compaction pass. None until a conversation grows past
    # the token budget, and safe to delete at any time — the turns themselves are kept,
    # so dropping it only costs context, never data.
    compaction: dict[str, Any] | None = None


@dataclass(slots=True)
class ConversationSummary:
    conversation_id: str
    title: str
    updated_at: datetime
    turn_count: int


_MEMORY: dict[tuple[str, str], ConversationRecord] = {}


def _visible_owners(user: str) -> tuple[str, ...]:
    # Version-1 rows had no owner. They are visible only to the demo administrator; there
    # is no defensible way to infer which ordinary user created them.
    return (user, "legacy") if user == "moneypal_admin" else (user,)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _title_from(question: str) -> str:
    q = " ".join(question.split())
    return q[:TITLE_MAX] + ("…" if len(q) > TITLE_MAX else "")


def _ensure_table() -> bool:
    global _table_ready
    if _table_ready:
        return True
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(DDL)
            for statement in MIGRATIONS:
                cur.execute(statement)
            conn.commit()
        _table_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench history table unavailable, using memory: %s", exc)
        return False


def _record_payload(record: ConversationRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": record.record_version,
        "title": record.title,
        "turns": record.turns,
    }
    if record.compaction:
        payload["compaction"] = record.compaction
    return payload


def _load(conversation_id: str, user: str) -> ConversationRecord | None:
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                owners = _visible_owners(user)
                cur.execute(
                    f"SELECT title, record_json, updated_at, owner_username, record_version "
                    f"FROM {TABLE} WHERE conversation_id = %s AND owner_username = ANY(%s) "
                    "ORDER BY CASE WHEN owner_username = %s THEN 0 ELSE 1 END LIMIT 1",
                    (conversation_id, list(owners), user),
                )
                row = cur.fetchone()
                conn.rollback()
            if row is None:
                return None
            payload = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            return ConversationRecord(
                conversation_id=conversation_id,
                title=row[0],
                updated_at=row[2],
                turns=list(payload.get("turns", [])),
                owner_username=row[3],
                record_version=row[4] or payload.get("version", 1),
                # Absent on v1/v2 rows; those conversations simply have no checkpoint yet.
                compaction=payload.get("compaction"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history load failed, using memory: %s", exc)
    for owner in _visible_owners(user):
        record = _MEMORY.get((owner, conversation_id))
        if record is not None:
            return record
    return None


def exists(conversation_id: str) -> bool:
    """Whether an id exists for any owner, used to reject cross-user id reuse."""
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(f"SELECT 1 FROM {TABLE} WHERE conversation_id = %s", (conversation_id,))
                found = cur.fetchone() is not None
                conn.rollback()
            return found
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history existence check failed: %s", exc)
    return any(cid == conversation_id for _, cid in _MEMORY)


def _save(record: ConversationRecord) -> None:
    record.updated_at = _now()
    # Upgrade on write: whatever version a record was read at, this module now writes the
    # current payload shape, so the stored version should say so.
    record.record_version = RECORD_VERSION
    _MEMORY[(record.owner_username, record.conversation_id)] = record
    if not _ensure_table():
        return
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(
                f"INSERT INTO {TABLE} "
                "(conversation_id, owner_username, title, record_version, record_json, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, now()) "
                "ON CONFLICT (conversation_id) DO UPDATE SET "
                "owner_username = EXCLUDED.owner_username, title = EXCLUDED.title, "
                "record_version = EXCLUDED.record_version, record_json = EXCLUDED.record_json, "
                "updated_at = now()",
                (
                    record.conversation_id,
                    record.owner_username,
                    record.title,
                    record.record_version,
                    json.dumps(_record_payload(record), default=str),
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench history write failed, retained in memory: %s", exc)


def set_compaction(conversation_id: str, user: str, payload: dict[str, Any] | None) -> None:
    """Store (or clear) the conversation checkpoint.

    Passing None discards it. That is the recovery path if a checkpoint ever proves
    misleading: the turns are all still present, so the next transcript simply rebuilds
    from them.
    """
    record = _load(conversation_id, user)
    if record is None:
        return
    record.compaction = payload
    _save(record)


def _mutate(
    conversation_id: str,
    user: str,
    turn_id: str,
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    record = _load(conversation_id, user)
    if record is None:
        return
    turn = next((item for item in record.turns if item.get("id") == turn_id), None)
    if turn is None:
        return
    mutation(turn)
    _save(record)


def begin_turn(
    conversation_id: str, user: str, question: str, *, pinned: str | None = None
) -> str:
    """Create the user half of a turn before routing or tool calls begin.

    `pinned` is recorded because it is a binding later turns depend on — "what does it
    say about X" means something different depending on which document was pinned — and
    compaction cannot reconstruct it from the answer text.
    """
    record = _load(conversation_id, user)
    if record is None:
        record = ConversationRecord(
            conversation_id=conversation_id,
            owner_username=user,
            title=_title_from(question),
            updated_at=_now(),
        )
    turn_id = uuid.uuid4().hex[:12]
    record.turns.append({
        "id": turn_id,
        "question": question,
        "pinned": pinned,
        "route": None,
        "sources": [],  # compatibility with version-1 clients
        "cards": [],
        "synthesis": None,
        "refusal": None,
        "error": None,
        "status": "running",
        "created_at": _now().isoformat(),
        "completed_at": None,
    })
    _save(record)
    return turn_id


def set_route(
    conversation_id: str,
    user: str,
    turn_id: str,
    *,
    sources: list[str],
    intent: str,
    model: str = "",
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["sources"] = list(sources)
        turn["route"] = {"sources": list(sources), "intent": intent, "model": model}

    _mutate(conversation_id, user, turn_id, apply)


def add_card(conversation_id: str, user: str, turn_id: str, card: dict[str, Any]) -> None:
    _mutate(conversation_id, user, turn_id, lambda turn: turn.setdefault("cards", []).append(card))


def set_synthesis(conversation_id: str, user: str, turn_id: str, text: str) -> None:
    _mutate(conversation_id, user, turn_id, lambda turn: turn.update(synthesis=text))


def set_usage(
    conversation_id: str,
    user: str,
    turn_id: str,
    *,
    prompt_tokens: int,
    completion_tokens: int = 0,
) -> None:
    """Record what the provider actually charged for this turn.

    The transcript budget is a token budget, and a measured prompt size beats any
    character heuristic. Only the last such measurement is needed — turns after it are
    estimated — but keeping it per turn makes the accounting debuggable.
    """
    def apply(turn: dict[str, Any]) -> None:
        turn["usage"] = {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
        }

    _mutate(conversation_id, user, turn_id, apply)


def set_refusal(conversation_id: str, user: str, turn_id: str, payload: dict[str, Any]) -> None:
    _mutate(conversation_id, user, turn_id, lambda turn: turn.update(refusal=payload))


def set_error(conversation_id: str, user: str, turn_id: str, message: str) -> None:
    _mutate(conversation_id, user, turn_id, lambda turn: turn.update(error=message))


def complete_turn(conversation_id: str, user: str, turn_id: str, *, partial: bool = False) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["status"] = "partial" if partial else "complete"
        turn["completed_at"] = _now().isoformat()

    _mutate(conversation_id, user, turn_id, apply)


def record_turn(
    conversation_id: str,
    question: str,
    sources: list[str],
    user: str = "anonymous",
) -> None:
    """Compatibility helper for callers/tests using the old one-shot API."""
    turn_id = begin_turn(conversation_id, user, question)
    set_route(conversation_id, user, turn_id, sources=sources, intent=question)
    complete_turn(conversation_id, user, turn_id)


def list_recent(limit: int = 50, *, user: str = "anonymous") -> list[ConversationSummary]:
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT conversation_id, title, updated_at, "
                    f"jsonb_array_length(record_json->'turns') FROM {TABLE} "
                    "WHERE owner_username = ANY(%s) ORDER BY updated_at DESC LIMIT %s",
                    (list(_visible_owners(user)), limit),
                )
                return [
                    ConversationSummary(conversation_id=r[0], title=r[1], updated_at=r[2],
                                        turn_count=r[3] or 0)
                    for r in cur.fetchall()
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history read failed, using memory: %s", exc)
    ordered = sorted(
        (record for (owner, _), record in _MEMORY.items() if owner in _visible_owners(user)),
        key=lambda record: record.updated_at,
        reverse=True,
    )[:limit]
    return [
        ConversationSummary(record.conversation_id, record.title, record.updated_at, len(record.turns))
        for record in ordered
    ]


def get(conversation_id: str, *, user: str = "anonymous") -> ConversationRecord | None:
    return _load(conversation_id, user)


@dataclass(slots=True)
class Transcript:
    """The model-facing view of a conversation, plus how tight the fit was."""

    messages: list[dict[str, str]] = field(default_factory=list)
    tokens: int = 0
    budget: int = 0
    # True when even the newest turn alone had to be clipped to fit. At that point the
    # conversation can no longer carry its own most recent exchange intact, and the only
    # real remedy is a fresh session.
    overflow: bool = False


def build_transcript(
    conversation_id: str,
    *,
    user: str,
    token_budget: int | None = None,
) -> Transcript:
    """Assemble the next model call's messages from this conversation and no other.

    Three layers, cheapest and most reliable first:

    1. the compaction summary, when one has been written (prose, may be lossy);
    2. the mechanically extracted session state — figures, sources, refusals — which is
       exact and is rebuilt from the turns on every call, so it never degrades;
    3. the most recent turns verbatim, as many as the token budget allows.

    Layers 1 and 2 precede every live turn, so each is capped at a share of the budget
    rather than given an open claim on it — otherwise the summary of a conversation could
    crowd out the conversation. Older turns that fit nowhere are dropped whole rather than
    clipped mid-sentence: whatever mattered about them is in layer 2.
    """
    from app.services.workbench.compaction import budget, state as session_state

    limit = budget.budget_tokens() if token_budget is None else token_budget
    result = Transcript(budget=limit)

    record = _load(conversation_id, user)
    if record is None:
        return result
    complete = [turn for turn in record.turns if turn.get("status") != "running"]
    if not complete:
        return result

    messages: list[dict[str, str]] = []
    spent = 0

    compaction = record.compaction if isinstance(record.compaction, dict) else None
    first_kept = str(compaction.get("first_kept_turn_id", "")) if compaction else ""
    summary = str(compaction.get("summary", "")).strip() if compaction else ""
    if summary:
        summary = budget.clip_to_tokens(summary, int(limit * budget.SUMMARY_SHARE))
        messages.append({"role": "system", "content": "Conversation checkpoint:\n\n" + summary})
        spent += budget.estimate_tokens(summary)

    # Turns already folded into the checkpoint are not replayed verbatim.
    _, live = _split_at_turn(complete, first_kept)
    # Recomputed from every turn rather than read back from the checkpoint: turns are
    # never deleted, so this is always exact and cannot go stale against a summary.
    state = session_state.from_turns(complete, _assistant_text)
    state = session_state.trim_to_fit(
        state, max(0, int(limit * budget.COMPRESSED_SHARE) - spent), budget.estimate_tokens
    )
    rendered = session_state.render(state)
    if rendered:
        messages.append({"role": "system", "content": rendered})
        spent += budget.estimate_tokens(rendered)

    pairs = [
        (str(turn.get("question", "")).strip(), _assistant_text(turn))
        for turn in live
    ]
    pairs = [(question, answer) for question, answer in pairs if question and answer]

    # Fill the remaining budget from the newest turn backwards, then restore order.
    kept: list[tuple[str, str]] = []
    for question, answer in reversed(pairs):
        cost = budget.estimate_tokens(question) + budget.estimate_tokens(answer)
        if kept and spent + cost > limit:
            break
        if not kept and spent + cost > limit:
            # The newest turn does not fit even on its own. Keep it — a transcript
            # without the current exchange is useless — but clip it so the request stays
            # inside the window, and flag that this conversation has run out of room.
            room = max(0, limit - spent - budget.estimate_tokens(question))
            answer = budget.clip_to_tokens(answer, room)
            cost = budget.estimate_tokens(question) + budget.estimate_tokens(answer)
            result.overflow = True
        kept.append((question, answer))
        spent += cost
    for question, answer in reversed(kept):
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})

    result.messages = messages
    result.tokens = spent
    return result


def transcript(
    conversation_id: str,
    *,
    user: str,
    token_budget: int | None = None,
) -> list[dict[str, str]]:
    """Messages only. See `build_transcript` for the budget and overflow detail."""
    return build_transcript(conversation_id, user=user, token_budget=token_budget).messages


def _split_at_turn(
    turns: list[dict[str, Any]], first_kept_turn_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split turns into (already checkpointed, still replayed verbatim)."""
    if not first_kept_turn_id:
        return [], turns
    for index, turn in enumerate(turns):
        if turn.get("id") == first_kept_turn_id:
            return turns[:index], turns[index:]
    # The pointer names a turn we no longer have; replaying everything is the safe miss.
    return [], turns


def assistant_text(turn: dict[str, Any]) -> str:
    """The model-facing rendering of a turn's answer.

    Public because compaction needs exactly the view the model was given — including the
    row cap in `_card_text` — rather than a second, subtly different flattening.
    """
    return _assistant_text(turn)


def _assistant_text(turn: dict[str, Any]) -> str:
    parts: list[str] = []
    if turn.get("synthesis"):
        parts.append(str(turn["synthesis"]))
    for card in turn.get("cards", []) or []:
        text = _card_text(card)
        if text:
            parts.append(text)
    refusal = turn.get("refusal")
    if isinstance(refusal, dict) and refusal.get("message"):
        parts.append(str(refusal["message"]))
    if turn.get("error"):
        parts.append(f"Error: {turn['error']}")
    if not parts and not turn.get("cards") and turn.get("sources"):
        # Version-1 records retained only question/source stubs.
        return "The answer from this older turn was not retained."
    return "\n\n".join(dict.fromkeys(parts))


def _card_text(card: dict[str, Any]) -> str:
    source = str(card.get("source", "source"))
    card_type = str(card.get("card_type", ""))
    payload = card.get("payload") if isinstance(card.get("payload"), dict) else {}
    if card_type == "chart":
        title = str(payload.get("title") or "Result")
        subtitle = str(payload.get("subtitle") or "")
        summary = str(payload.get("summary") or "")
        chart_type = str(payload.get("chart_type") or "")
        columns = payload.get("columns") if isinstance(payload.get("columns"), list) else []
        fields = [
            str(column.get("name")) for column in columns
            if isinstance(column, dict) and column.get("name")
        ]
        chart_context = ""
        if chart_type or fields:
            chart_context = (
                f"Chart context: type={chart_type or 'unspecified'}; "
                f"fields={','.join(fields) or 'unspecified'}"
            )
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        row_lines = [json.dumps(row, default=str, ensure_ascii=False) for row in rows[:CARD_ROWS_IN_CONTEXT]]
        omitted = len(rows) - len(row_lines)
        body = "\n".join(row_lines)
        if omitted > 0:
            body += f"\n[{omitted} additional rows omitted from model context]"
        return "\n".join(
            part for part in [f"[{source}] {title}", subtitle, chart_context, body, summary]
            if part
        )
    if card_type == "analysis":
        # An analysis carries its whole answer in the findings, not in a row grid. Falling
        # through to the generic branch below returned "" for every one of them, so a
        # compacted thread lost the briefing entirely — and the follow-up "why is that?"
        # then had nothing to refer back to.
        title = str(payload.get("title") or "Analysis")
        headline = str(payload.get("headline") or "")
        findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
        lines = [
            f"- {finding.get('label')}: {finding.get('text')}"
            for finding in findings
            if isinstance(finding, dict) and finding.get("text")
        ]
        narrative = str(payload.get("narrative") or "")
        return "\n".join(
            part for part in [f"[{source}] {title}", headline, *lines, narrative] if part
        )
    if card_type == "brief":
        summary = str(payload.get("summary") or "")
        points = payload.get("key_points") if isinstance(payload.get("key_points"), list) else []
        return "\n".join([f"[{source}] {summary}", *(f"- {point}" for point in points)])
    if card_type == "schema":
        return f"[{source}] Schema: {payload.get('node_count', 0)} tables, {payload.get('edge_count', 0)} relationships."
    return str(payload.get("message") or payload.get("question") or "")
