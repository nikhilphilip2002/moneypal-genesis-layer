"""Durable, user-owned Workbench conversations and exact native-tool replay."""

from __future__ import annotations

import json
import logging
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.config import settings
from app.services.nlq.llm.messages import ChatMessage

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
RECORD_VERSION = 10
KNOWN_RECORD_VERSIONS = frozenset({9, RECORD_VERSION})
_table_ready = False
HISTORY_DB_RETRY_S = 10.0
_table_retry_after = 0.0


@dataclass(slots=True)
class ConversationRecord:
    conversation_id: str
    title: str
    updated_at: datetime
    turns: list[dict[str, Any]] = field(default_factory=list)
    owner_username: str = "anonymous"
    record_version: int = RECORD_VERSION
    compaction: dict[str, Any] | None = None
    external_sources_enabled: bool = False
    messages: list[ChatMessage] = field(default_factory=list)
    migration: dict[str, Any] | None = None


@dataclass(slots=True)
class ConversationSummary:
    conversation_id: str
    title: str
    updated_at: datetime
    turn_count: int


class UnknownRecordVersion(ValueError):
    """The record was written by a backend this module does not understand."""


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
    global _table_ready, _table_retry_after
    if _table_ready:
        return True
    if time.monotonic() < _table_retry_after:
        return False
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
        _table_retry_after = time.monotonic() + HISTORY_DB_RETRY_S
        logger.warning(
            "workbench history table unavailable; using memory and retrying in %.0fs: %s",
            HISTORY_DB_RETRY_S,
            exc,
        )
        return False


def _record_payload(record: ConversationRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": record.record_version,
        "title": record.title,
        "turns": record.turns,
        "messages": record.messages,
        "migration": record.migration,
    }
    if record.compaction:
        payload["compaction"] = record.compaction
    payload["external_sources_enabled"] = record.external_sources_enabled
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
            payload = (
                row[1] if isinstance(row[1], dict) else json.loads(row[1])
            )
            stored_version = row[4] or payload.get("version", 1)
            if stored_version not in KNOWN_RECORD_VERSIONS:
                raise UnknownRecordVersion(
                    f"conversation {conversation_id} is record version {stored_version!r}; "
                    f"this backend requires version {RECORD_VERSION}"
                )
            record = ConversationRecord(
                conversation_id=conversation_id,
                title=row[0],
                updated_at=row[2],
                turns=list(payload.get("turns", [])),
                owner_username=row[3],
                record_version=stored_version,
                compaction=payload.get("compaction"),
                external_sources_enabled=bool(
                    payload.get("external_sources_enabled", False)
                ),
                messages=list(payload.get("messages", [])),
                migration=payload.get("migration"),
            )
            _migrate_record(record)
            return record
        except UnknownRecordVersion:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "workbench history load failed, using memory: %s", exc
            )
    for owner in _visible_owners(user):
        record = _MEMORY.get((owner, conversation_id))
        if record is not None:
            if record.record_version not in KNOWN_RECORD_VERSIONS:
                raise UnknownRecordVersion(
                    f"conversation {conversation_id} is record version "
                    f"{record.record_version!r}; this backend requires version "
                    f"{RECORD_VERSION}"
                )
            _migrate_record(record)
            return record
    return None


def _migrate_record(record: ConversationRecord) -> None:
    if record.record_version == RECORD_VERSION:
        return
    from app.services.workbench.history_migration import migrate_messages

    record.messages = migrate_messages(record.turns)
    record.migration = {
        "from_version": record.record_version,
        "message_count": len(record.messages),
        "previous_compaction": record.compaction,
    }
    record.compaction = None
    record.record_version = RECORD_VERSION
    _save(record)


def append_messages(
    conversation_id: str,
    user: str,
    turn_id: str,
    messages: list[ChatMessage],
) -> None:
    record = _load(conversation_id, user)
    if record is None:
        raise ValueError("conversation does not exist")
    turn = next(item for item in record.turns if item["id"] == turn_id)
    pending = pending_tool_calls(record.messages)
    for message in messages:
        if message["role"] == "tool":
            if not pending or message.get("tool_call_id") != pending[0]:
                raise ValueError(
                    "tool results must match pending calls in order"
                )
            pending.pop(0)
        else:
            if pending:
                raise ValueError(
                    "pending tool calls require results before continuation"
                )
            pending = [call["id"] for call in message.get("tool_calls") or []]
            if len(pending) != len(set(pending)):
                raise ValueError(
                    "duplicate tool call IDs in assistant message"
                )
    start = len(record.messages)
    turn.setdefault("message_start", start)
    record.messages.extend(deepcopy(messages))
    turn["message_end"] = len(record.messages)
    _save(record)


def load_messages(conversation_id: str, *, user: str) -> list[ChatMessage]:
    record = _load(conversation_id, user)
    return deepcopy(record.messages) if record is not None else []


def set_checkpoint(
    conversation_id: str, user: str, checkpoint: dict[str, Any]
) -> None:
    record = _load(conversation_id, user)
    if record is None:
        raise ValueError("conversation does not exist")
    record.compaction = deepcopy(checkpoint)
    _save(record)


def pending_tool_calls(messages: list[ChatMessage]) -> list[str]:
    pending: dict[str, None] = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            pending[call["id"]] = None
        if message.get("role") == "tool":
            pending.pop(str(message.get("tool_call_id", "")), None)
    return list(pending)


def interrupted_tool_result(call_id: str) -> ChatMessage:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(
            {
                "status": "error",
                "code": "INTERRUPTED",
                "message": "Execution was interrupted; no result was recorded.",
            },
            separators=(",", ":"),
        ),
    }


def start_turn_messages(
    conversation_id: str,
    user: str,
    turn_id: str,
    system: ChatMessage,
    question: ChatMessage,
) -> ConversationRecord:
    record = _load(conversation_id, user)
    if record is None:
        raise ValueError("conversation does not exist")
    turn = next(item for item in record.turns if item["id"] == turn_id)
    if not record.messages or record.messages[0]["role"] != "system":
        record.messages.insert(0, deepcopy(system))
        for previous in record.turns:
            for key in ("message_start", "message_end"):
                if key in previous:
                    previous[key] += 1
    elif record.messages[0] != system:
        turn["previous_system_message"] = deepcopy(record.messages[0])
        record.messages[0] = deepcopy(system)
    record.messages.extend(
        interrupted_tool_result(call_id)
        for call_id in pending_tool_calls(record.messages)
    )
    for previous in record.turns:
        if previous["id"] != turn_id and previous.get("status") == "running":
            previous["status"] = "partial"
            previous["completed_at"] = _now().isoformat()
            previous["message_end"] = len(record.messages)
    turn["message_start"] = len(record.messages)
    record.messages.append(deepcopy(question))
    turn["message_end"] = len(record.messages)
    _save(record)
    return record


def exists(conversation_id: str) -> bool:
    """Whether an id exists for any owner, used to reject cross-user id reuse."""
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT 1 FROM {TABLE} WHERE conversation_id = %s",
                    (conversation_id,),
                )
                found = cur.fetchone() is not None
                conn.rollback()
            return found
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history existence check failed: %s", exc)
    return any(cid == conversation_id for _, cid in _MEMORY)


def _save(record: ConversationRecord) -> None:
    if record.record_version not in KNOWN_RECORD_VERSIONS:
        # Never downgrade a record a newer backend wrote: the payload shape it carries
        # may hold fields this module would silently drop.
        raise UnknownRecordVersion(
            f"conversation {record.conversation_id} is record version "
            f"{record.record_version!r}; this backend understands versions "
            f"{RECORD_VERSION}"
        )
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
        logger.warning(
            "workbench history write failed, retained in memory: %s", exc
        )


def _mutate(
    conversation_id: str,
    user: str,
    turn_id: str,
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    record = _load(conversation_id, user)
    if record is None:
        return
    turn = next(
        (item for item in record.turns if item.get("id") == turn_id), None
    )
    if turn is None:
        return
    mutation(turn)
    _save(record)


def begin_turn(
    conversation_id: str,
    user: str,
    question: str,
    *,
    pinned: str | None = None,
    source_policy: dict[str, Any] | None = None,
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
    if source_policy is not None:
        record.external_sources_enabled = bool(
            source_policy.get("external_sources_enabled", False)
        )
    created_at = _now()
    record.turns.append(
        {
            "id": turn_id,
            "question": question,
            "pinned": pinned,
            "source_policy": source_policy,
            "route": None,
            "sources": [],  # compatibility with version-1 clients
            "cards": [],
            "query_registry": [],
            "answer": None,
            "synthesis": None,
            "refusal": None,
            "error": None,
            "error_details": None,
            "status": "running",
            "created_at": created_at.isoformat(),
            "completed_at": None,
        }
    )
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
    reason: str = "",
    effective_sources: list[str] | tuple[str, ...] = (),
    tools: list[str] | tuple[str, ...] = (),
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["sources"] = list(sources)
        turn["route"] = {
            "sources": list(sources),
            "intent": intent,
            "model": model,
            "reason": reason,
            "effective_sources": list(effective_sources),
            "tools": list(tools),
        }

    _mutate(conversation_id, user, turn_id, apply)


def set_query_registry(
    conversation_id: str,
    user: str,
    turn_id: str,
    registry: list[dict[str, Any]],
) -> None:
    """Persist the current authoritative database-query registry for a turn."""

    snapshot = [dict(item) for item in registry if isinstance(item, dict)]

    def apply(turn: dict[str, Any]) -> None:
        turn["query_registry"] = snapshot

    _mutate(conversation_id, user, turn_id, apply)


def add_card(
    conversation_id: str, user: str, turn_id: str, card: dict[str, Any]
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn.setdefault("cards", []).append(deepcopy(card))

    _mutate(conversation_id, user, turn_id, apply)


def set_answer(
    conversation_id: str, user: str, turn_id: str, payload: dict[str, Any]
) -> None:
    """Persist the one user-facing answer while keeping `synthesis` for old clients."""

    def apply(turn: dict[str, Any]) -> None:
        turn["answer"] = payload
        turn["synthesis"] = str(payload.get("text", "")) or None

    _mutate(conversation_id, user, turn_id, apply)


def set_usage(
    conversation_id: str,
    user: str,
    turn_id: str,
    *,
    prompt_tokens: int,
    completion_tokens: int = 0,
    total_prompt_tokens: int | None = None,
    cached_prompt_tokens: int = 0,
    cache_write_prompt_tokens: int = 0,
    uncached_prompt_tokens: int | None = None,
    model_duration_ms: int = 0,
    model_call_count: int = 0,
    retry_count: int = 0,
    weighted_input_units: float = 0.0,
    tool_call_count: int = 0,
    tool_names: list[str] | tuple[str, ...] | None = None,
    calls: list[dict[str, Any]] | None = None,
) -> None:
    """Record what the provider actually charged for this turn.

    The transcript budget is a token budget, and a measured prompt size beats any
    character heuristic. Only the last such measurement is needed — turns after it are
    estimated — but keeping it per turn makes the accounting debuggable.
    """

    def apply(turn: dict[str, Any]) -> None:
        turn["usage"] = {
            "prompt_tokens": int(prompt_tokens),
            "total_prompt_tokens": int(
                prompt_tokens
                if total_prompt_tokens is None
                else total_prompt_tokens
            ),
            "cached_prompt_tokens": int(cached_prompt_tokens),
            "cache_write_prompt_tokens": int(cache_write_prompt_tokens),
            "uncached_prompt_tokens": int(
                max(0, prompt_tokens - cached_prompt_tokens)
                if uncached_prompt_tokens is None
                else uncached_prompt_tokens
            ),
            "completion_tokens": int(completion_tokens),
            "model_duration_ms": int(model_duration_ms),
            "model_call_count": int(model_call_count),
            "retry_count": int(retry_count),
            "weighted_input_units": float(weighted_input_units),
            "tool_call_count": int(tool_call_count),
            "tool_names": list(tool_names or []),
            "calls": list(calls or []),
        }

    _mutate(conversation_id, user, turn_id, apply)


def set_timing(
    conversation_id: str,
    user: str,
    turn_id: str,
    *,
    first_event_ms: int = 0,
    first_card_ms: int = 0,
    final_answer_ms: int = 0,
    total_ms: int = 0,
    source_attempts: list[str] | None = None,
    source_completions: list[str] | None = None,
) -> None:
    """Persist end-to-end streaming latency and connector-operation counters."""

    def apply(turn: dict[str, Any]) -> None:
        turn["timing"] = {
            "first_event_ms": int(first_event_ms),
            "first_card_ms": int(first_card_ms),
            "final_answer_ms": int(final_answer_ms),
            "total_ms": int(total_ms),
            "source_attempts": list(source_attempts or []),
            "source_completions": list(source_completions or []),
        }

    _mutate(conversation_id, user, turn_id, apply)


def set_execution_trace(
    conversation_id: str,
    user: str,
    turn_id: str,
    *,
    trace: list[dict[str, Any]],
) -> None:
    """Persist the safe user-visible execution trace after streaming completes.

    This deliberately excludes provider reasoning content. Tool arguments have already
    been display-sanitized by the agent before they reach this field.
    """

    def apply(turn: dict[str, Any]) -> None:
        turn["execution_trace"] = [
            dict(step) for step in trace if isinstance(step, dict)
        ]

    _mutate(conversation_id, user, turn_id, apply)


def set_refusal(
    conversation_id: str, user: str, turn_id: str, payload: dict[str, Any]
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["refusal"] = payload

    _mutate(conversation_id, user, turn_id, apply)


def set_error(
    conversation_id: str,
    user: str,
    turn_id: str,
    message: str,
    *,
    code: str | None = None,
    retryable: bool | None = None,
    reason: str | None = None,
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["error"] = message
        details = {
            "message": message,
            **({"code": code} if code else {}),
            **({"retryable": retryable} if retryable is not None else {}),
            **({"reason": reason} if reason else {}),
        }
        turn["error_details"] = details

    _mutate(conversation_id, user, turn_id, apply)


def complete_turn(
    conversation_id: str, user: str, turn_id: str, *, partial: bool = False
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["status"] = "partial" if partial else "complete"
        turn["completed_at"] = _now().isoformat()

    _mutate(conversation_id, user, turn_id, apply)


def list_recent(
    limit: int = 50, *, user: str = "anonymous"
) -> list[ConversationSummary]:
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(
                    f"SELECT conversation_id, title, updated_at, "
                    f"jsonb_array_length(record_json->'turns') FROM {TABLE} "
                    "WHERE owner_username = ANY(%s) AND record_version = ANY(%s) "
                    "ORDER BY updated_at DESC LIMIT %s",
                    (
                        list(_visible_owners(user)),
                        sorted(KNOWN_RECORD_VERSIONS),
                        limit,
                    ),
                )
                return [
                    ConversationSummary(
                        conversation_id=r[0],
                        title=r[1],
                        updated_at=r[2],
                        turn_count=r[3] or 0,
                    )
                    for r in cur.fetchall()
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "workbench history read failed, using memory: %s", exc
            )
    ordered = sorted(
        (
            record
            for (owner, _), record in _MEMORY.items()
            if owner in _visible_owners(user)
            and record.record_version in KNOWN_RECORD_VERSIONS
        ),
        key=lambda record: record.updated_at,
        reverse=True,
    )[:limit]
    return [
        ConversationSummary(
            record.conversation_id,
            record.title,
            record.updated_at,
            len(record.turns),
        )
        for record in ordered
    ]


def get(
    conversation_id: str, *, user: str = "anonymous"
) -> ConversationRecord | None:
    return _load(conversation_id, user)


def previous_query_registry(
    conversation_id: str,
    *,
    user: str,
    turn_id: str,
) -> list[dict[str, Any]]:
    """Return earlier query attempts from this user-owned conversation, in turn order."""
    record = _load(conversation_id, user)
    if record is None:
        return []
    previous: list[dict[str, Any]] = []
    for turn in record.turns:
        if turn.get("id") == turn_id:
            break
        registry = turn.get("query_registry")
        if isinstance(registry, list):
            previous.extend(
                dict(item) for item in registry if isinstance(item, dict)
            )
    return previous


def private_entities(conversation_id: str, *, user: str) -> tuple[str, ...]:
    """Return exact previously selected private entity values for outbound screening."""
    record = _load(conversation_id, user)
    if record is None:
        return ()
    values: list[str] = []
    for message in record.messages:
        for raw_call in message.get("tool_calls") or []:
            call = raw_call["function"]
            try:
                arguments = json.loads(call["arguments"])
            except (ValueError, TypeError):
                continue
            if not isinstance(arguments, dict):
                continue
            if (
                call.get("name") == "lookup_records"
            ):  # version-7 history compatibility
                value = arguments.get("value")
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
                continue
            if call.get("name") not in settings.postgres_mcp_model_tools:
                continue
            sql = arguments.get("sql")
            if not isinstance(sql, str) or not sql.strip():
                continue
            try:
                from sqlglot import exp, parse_one

                tree = parse_one(sql, read="postgres")
                values.extend(
                    str(literal.this).strip()
                    for literal in tree.find_all(exp.Literal)
                    if literal.is_string
                    and len(str(literal.this).strip()) >= 2
                )
            except Exception:  # noqa: BLE001 - malformed historical SQL contributes no entities
                logger.debug(
                    "could not extract private literals from historical MCP SQL"
                )
    return tuple(dict.fromkeys(values[-20:]))
