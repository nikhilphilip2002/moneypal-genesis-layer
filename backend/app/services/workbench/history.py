"""Durable conversation history for the workbench.

Persisted to Postgres so a conversation list survives a restart; an in-memory dict is the
fallback when no database is configured, mirroring how the NLQ conversation store degrades.
Records are deliberately light — a title and one stub per turn (question + which sources
answered) — enough to populate the History rail without storing every rendered card.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TABLE = "public.workbench_conversations"
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    conversation_id text PRIMARY KEY,
    title           text NOT NULL,
    record_json     jsonb NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
"""

TITLE_MAX = 80
_table_ready = False


@dataclass(slots=True)
class ConversationRecord:
    conversation_id: str
    title: str
    updated_at: datetime
    turns: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class ConversationSummary:
    conversation_id: str
    title: str
    updated_at: datetime
    turn_count: int


# In-memory fallback / dev store.
_MEMORY: dict[str, ConversationRecord] = {}


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
            conn.commit()
        _table_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench history table unavailable, using memory: %s", exc)
        return False


def record_turn(conversation_id: str, question: str, sources: list[str]) -> None:
    """Append a turn to a conversation, creating it (and its title) on the first turn."""
    turn = {"question": question, "sources": list(sources), "at": _now().isoformat()}

    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(f"SELECT record_json FROM {TABLE} WHERE conversation_id = %s",
                            (conversation_id,))
                row = cur.fetchone()
                if row:
                    record = row[0]
                    record["turns"].append(turn)
                    title = record.get("title") or _title_from(question)
                else:
                    title = _title_from(question)
                    record = {"title": title, "turns": [turn]}
                import json

                cur.execute(
                    f"INSERT INTO {TABLE} (conversation_id, title, record_json, updated_at) "
                    "VALUES (%s, %s, %s, now()) ON CONFLICT (conversation_id) DO UPDATE "
                    "SET title = EXCLUDED.title, record_json = EXCLUDED.record_json, "
                    "updated_at = now()",
                    (conversation_id, title, json.dumps(record)),
                )
                conn.commit()
            return
        except Exception as exc:  # noqa: BLE001 - fall through to memory rather than 500
            logger.warning("workbench history write failed, using memory: %s", exc)

    rec = _MEMORY.get(conversation_id)
    if rec is None:
        _MEMORY[conversation_id] = ConversationRecord(
            conversation_id=conversation_id, title=_title_from(question),
            updated_at=_now(), turns=[turn],
        )
    else:
        rec.turns.append(turn)
        rec.updated_at = _now()


def list_recent(limit: int = 50) -> list[ConversationSummary]:
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT conversation_id, title, updated_at, "
                    f"jsonb_array_length(record_json->'turns') FROM {TABLE} "
                    "ORDER BY updated_at DESC LIMIT %s",
                    (limit,),
                )
                return [
                    ConversationSummary(conversation_id=r[0], title=r[1], updated_at=r[2],
                                        turn_count=r[3] or 0)
                    for r in cur.fetchall()
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history read failed, using memory: %s", exc)

    ordered = sorted(_MEMORY.values(), key=lambda r: r.updated_at, reverse=True)[:limit]
    return [
        ConversationSummary(conversation_id=r.conversation_id, title=r.title,
                            updated_at=r.updated_at, turn_count=len(r.turns))
        for r in ordered
    ]


def get(conversation_id: str) -> ConversationRecord | None:
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT title, record_json, updated_at FROM {TABLE} WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return ConversationRecord(conversation_id=conversation_id, title=row[0],
                                          updated_at=row[2], turns=row[1].get("turns", []))
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history load failed, using memory: %s", exc)

    return _MEMORY.get(conversation_id)
