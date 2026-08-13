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
RECORD_VERSION = 2
# 80k characters is roughly 20k tokens. This leaves room in a 32k context for the router
# or planner system prompt, catalog/schema grammar, the current question, and output.
TRANSCRIPT_CHAR_BUDGET = 80_000
RECENT_TURNS_VERBATIM = 8
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
    return {
        "version": record.record_version,
        "title": record.title,
        "turns": record.turns,
    }


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


def begin_turn(conversation_id: str, user: str, question: str) -> str:
    """Create the user half of a turn before routing or tool calls begin."""
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


def transcript(
    conversation_id: str,
    *,
    user: str,
    char_budget: int = TRANSCRIPT_CHAR_BUDGET,
) -> list[dict[str, str]]:
    """Role messages for the next model call, from this conversation and no other."""
    record = _load(conversation_id, user)
    if record is None:
        return []
    complete = [turn for turn in record.turns if turn.get("status") != "running"]
    pairs = [(str(turn.get("question", "")).strip(), _assistant_text(turn)) for turn in complete]
    pairs = [(question, answer) for question, answer in pairs if question and answer]
    if not pairs:
        return []

    total_chars = sum(len(question) + len(answer) for question, answer in pairs)
    if total_chars <= char_budget:
        return [
            message
            for question, answer in pairs
            for message in (
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            )
        ]

    # Keep the most recent turns verbatim. Older turns become deterministic session memory
    # only when needed; no second model call is required merely to maintain context.
    recent = pairs[-RECENT_TURNS_VERBATIM:]
    older = pairs[:-RECENT_TURNS_VERBATIM]
    recent_chars = sum(len(question) + len(answer) for question, answer in recent)
    while recent and recent_chars > char_budget:
        older.append(recent.pop(0))
        recent_chars = sum(len(question) + len(answer) for question, answer in recent)

    messages: list[dict[str, str]] = []
    remaining = max(0, char_budget - recent_chars)
    if older and remaining:
        memory_lines = []
        for question, answer in older:
            line = f"User: {question}\nAssistant: {answer}"[:OLDER_TURN_MAX_CHARS]
            if sum(len(item) for item in memory_lines) + len(line) > remaining:
                break
            memory_lines.append(line)
        if memory_lines:
            messages.append({
                "role": "system",
                "content": "Earlier conversation memory:\n\n" + "\n\n".join(memory_lines),
            })
    for question, answer in recent:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    return messages


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
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        row_lines = [json.dumps(row, default=str, ensure_ascii=False) for row in rows[:CARD_ROWS_IN_CONTEXT]]
        omitted = len(rows) - len(row_lines)
        body = "\n".join(row_lines)
        if omitted > 0:
            body += f"\n[{omitted} additional rows omitted from model context]"
        return "\n".join(part for part in [f"[{source}] {title}", subtitle, body, summary] if part)
    if card_type == "brief":
        summary = str(payload.get("summary") or "")
        points = payload.get("key_points") if isinstance(payload.get("key_points"), list) else []
        return "\n".join([f"[{source}] {summary}", *(f"- {point}" for point in points)])
    if card_type == "schema":
        return f"[{source}] Schema: {payload.get('node_count', 0)} tables, {payload.get('edge_count', 0)} relationships."
    return str(payload.get("message") or payload.get("question") or "")
