"""Durable, user-owned Workbench conversations and exact native-tool replay."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
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
# v6 added an ordered execution event stream and lossless native tool-result replay.
# v7 makes that stream the only representation: every turn carries `events`, readers
# derive everything from them, and older turns are migrated rather than read sideways.
RECORD_VERSION = 7
# Every version this module can read. A record stamped with anything else was written by
# a newer backend and must not be overwritten by this one.
KNOWN_RECORD_VERSIONS = frozenset(range(1, RECORD_VERSION + 1))
CARD_ROWS_IN_CONTEXT = 20
# Replay policy: which event kinds of a turn are sent back to the provider. Nudges and
# other synthetic user messages are stored so the record is the exact transcript, but
# they are not resent — the next turn's own nudge is appended live.
REPLAYED_SYSTEM_MESSAGE_KINDS: frozenset[str] = frozenset()
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
    # Checkpoint written by the compaction pass. None until a conversation grows past
    # the token budget, and safe to delete at any time — the turns themselves are kept,
    # so dropping it only costs context, never data.
    compaction: dict[str, Any] | None = None
    external_sources_enabled: bool = False


@dataclass(slots=True)
class ConversationSummary:
    conversation_id: str
    title: str
    updated_at: datetime
    turn_count: int


class NativeTranscriptOverflow(RuntimeError):
    """The exact native transcript cannot fit without silently dropping history.

    ``reason`` says which remedy can help: ``conversation_exceeds_budget`` means older
    turns could be checkpointed; ``single_turn_exceeds_budget`` means the newest turn
    alone is too large and only a fresh conversation helps.
    """

    def __init__(self, message: str, *, reason: str = "conversation_exceeds_budget") -> None:
        super().__init__(f"{message} (reason: {reason})")
        self.reason = reason


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
            payload = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            record = ConversationRecord(
                conversation_id=conversation_id,
                title=row[0],
                updated_at=row[2],
                turns=list(payload.get("turns", [])),
                owner_username=row[3],
                record_version=row[4] or payload.get("version", 1),
                # Absent on v1/v2 rows; those conversations simply have no checkpoint yet.
                compaction=payload.get("compaction"),
                external_sources_enabled=bool(payload.get("external_sources_enabled", False)),
            )
            # Older turns are given their event stream in memory so every reader sees one
            # representation; the next write persists it and stamps the version.
            migrate_record(record)
            return record
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench history load failed, using memory: %s", exc)
    for owner in _visible_owners(user):
        record = _MEMORY.get((owner, conversation_id))
        if record is not None:
            migrate_record(record)
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
    if record.record_version not in KNOWN_RECORD_VERSIONS:
        # Never downgrade a record a newer backend wrote: the payload shape it carries
        # may hold fields this module would silently drop.
        raise UnknownRecordVersion(
            f"conversation {record.conversation_id} is record version "
            f"{record.record_version!r}; this backend understands versions "
            f"1..{RECORD_VERSION}"
        )
    record.updated_at = _now()
    # The version is a schema signal, not a stamp: it says 7 only when every turn carries
    # its event stream. `_load` migrates older turns in memory, so ordinarily it does.
    if all(turn_has_events(turn) for turn in record.turns):
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


def set_compaction(
    conversation_id: str, user: str, payload: dict[str, Any] | None, *,
    replaced_turn_ids: list[str] | tuple[str, ...] = (),
) -> None:
    """Store (or clear) the conversation checkpoint.

    The checkpoint pointer on the record is what replay consults; the summary itself is
    also appended as a ``compaction_summary`` event on the newest turn it replaces, naming
    every turn it stands in for. No event is ever removed: compaction adds a view, it
    never edits the durable record.

    Passing None discards the pointer. That is the recovery path if a checkpoint ever
    proves misleading: the turns are all still present, so the next transcript simply
    rebuilds from them.
    """
    record = _load(conversation_id, user)
    if record is None:
        return
    record.compaction = payload
    replaced = [str(turn_id) for turn_id in replaced_turn_ids if turn_id]
    if payload and replaced:
        anchor = next(
            (turn for turn in reversed(record.turns) if turn.get("id") == replaced[-1]), None,
        )
        if anchor is not None:
            _append_turn_event(anchor, "compaction_summary", {
                "summary": str(payload.get("summary", "")),
                "replaces_turn_ids": replaced,
                "first_kept_turn_id": str(payload.get("first_kept_turn_id", "")),
                "created_at": str(payload.get("created_at", "")),
            })
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


def _append_turn_event(
    turn: dict[str, Any], event_type: str, payload: dict[str, Any], *,
    timestamp: str | None = None, derived: bool = False,
) -> dict[str, Any]:
    """Append one ordered, lossless conversation execution event."""
    events = turn.setdefault("events", [])
    event: dict[str, Any] = {
        "sequence": len(events),
        "type": event_type,
        "timestamp": timestamp or _now().isoformat(),
        "payload": payload,
    }
    if derived:
        # Reconstructed by the version-7 migration from the older per-field copies, not
        # observed live; the timestamp is the turn's, not the event's.
        event["derived"] = True
    events.append(event)
    return event


def turn_has_events(turn: dict[str, Any]) -> bool:
    events = turn.get("events")
    return isinstance(events, list) and len(events) > 0


def turn_events(turn: dict[str, Any]) -> list[dict[str, Any]]:
    """The ordered event stream of a turn, derived on the fly for a pre-v7 turn dict."""
    if turn_has_events(turn):
        return [event for event in turn["events"] if isinstance(event, dict)]
    return derive_turn_events(turn)


def _parsed_tool_content(message: dict[str, Any]) -> dict[str, Any] | None:
    content = message.get("content")
    if not isinstance(content, str) or not content.startswith("{"):
        return None
    try:
        parsed = json.loads(content)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _sql_trace_of(message: dict[str, Any]) -> list[dict[str, Any]]:
    """The nested text-to-SQL rounds a governed call went through, oldest first."""
    parsed = _parsed_tool_content(message)
    if parsed is None:
        return []
    lineage = parsed.get("lineage")
    nested = lineage.get("text_to_sql") if isinstance(lineage, dict) else None
    trace = nested.get("trace") if isinstance(nested, dict) else None
    if not isinstance(trace, list):
        return []
    return [item for item in trace if isinstance(item, dict)]


def _append_native_exchange_events(
    turn: dict[str, Any], *, assistant: ChatMessage, calls: list[dict[str, Any]],
    tool_messages: list[dict[str, Any]], stage: str, timestamp: str | None = None,
    derived: bool = False,
) -> None:
    """One assistant message, then per call its ``tool_call`` and the ordered child
    ``text_to_sql_attempt`` events of any nested generation it ran, then the results."""
    results_by_call = {
        str(message.get("tool_call_id", "")): message for message in tool_messages
    }
    _append_turn_event(turn, "llm_assistant_message", {
        "execution_path": "native",
        "stage": stage,
        "message": assistant,
    }, timestamp=timestamp, derived=derived)
    for call in calls:
        parent = _append_turn_event(turn, "tool_call", {
            "execution_path": "native",
            "call": call,
        }, timestamp=timestamp, derived=derived)
        result = results_by_call.get(str(call.get("id", "")))
        for index, item in enumerate(_sql_trace_of(result) if result else []):
            _append_turn_event(turn, "text_to_sql_attempt", {
                "execution_path": "native_child",
                "parent_sequence": parent["sequence"],
                "parent_call_id": str(call.get("id", "")),
                "index": index,
                "attempt": item,
            }, timestamp=timestamp, derived=derived)
    for message in tool_messages:
        _append_turn_event(turn, "tool_result", {
            "execution_path": "native",
            "message": dict(message),
        }, timestamp=timestamp, derived=derived)


def derive_turn_events(turn: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild a turn's event stream from the per-field copies pre-v7 records kept.

    Order follows execution: the question, the route, each native exchange, the rendered
    cards, the synthesis candidate, the answer or refusal, then the error. The result is
    what a v7 writer would have recorded, so replay over it equals the replay the old
    sideways readers produced.
    """
    shadow: dict[str, Any] = {"events": []}
    created = str(turn.get("created_at") or turn.get("at") or "")
    completed = str(turn.get("completed_at") or created)
    _append_turn_event(shadow, "user_message", {
        "role": "user", "content": str(turn.get("question", "")),
    }, timestamp=created or None, derived=True)
    route = turn.get("route")
    if isinstance(route, dict):
        _append_turn_event(shadow, "route_decision", dict(route), timestamp=created or None, derived=True)
    for exchange in turn.get("agent_exchanges") or []:
        if not isinstance(exchange, dict):
            continue
        assistant = exchange.get("assistant")
        tools = exchange.get("tools")
        if not isinstance(assistant, dict) or not isinstance(tools, list):
            continue
        calls = [call for call in exchange.get("calls") or [] if isinstance(call, dict)]
        _append_native_exchange_events(
            shadow, assistant=dict(assistant), calls=calls,
            tool_messages=[dict(item) for item in tools if isinstance(item, dict)],
            stage="route", timestamp=completed or None, derived=True,
        )
    for card in turn.get("cards") or []:
        if isinstance(card, dict):
            _append_turn_event(shadow, "tool_result", {
                "execution_path": "legacy_or_rendered",
                "card": card,
            }, timestamp=completed or None, derived=True)
    answer = turn.get("answer") if isinstance(turn.get("answer"), dict) else None
    synthesis = turn.get("synthesis")
    if synthesis and (answer is None or str(answer.get("text", "")) != str(synthesis)):
        _append_turn_event(shadow, "llm_assistant_message", {
            "execution_path": "synthesis",
            "stage": "synthesize",
            "candidate": True,
            "message": {"role": "assistant", "content": str(synthesis)},
        }, timestamp=completed or None, derived=True)
    if answer is not None:
        _append_turn_event(shadow, "final_answer", {"answer": answer}, timestamp=completed or None, derived=True)
    refusal = turn.get("refusal")
    if isinstance(refusal, dict):
        _append_turn_event(shadow, "final_answer", {"refusal": refusal}, timestamp=completed or None, derived=True)
    if turn.get("error"):
        details = turn.get("error_details")
        payload = (
            dict(details)
            if isinstance(details, dict)
            else {"message": str(turn["error"])}
        )
        _append_turn_event(
            shadow, "execution_error", payload,
            timestamp=completed or None, derived=True,
        )
    return shadow["events"]


def migrate_turn(turn: dict[str, Any]) -> bool:
    """Give a pre-v7 turn its event stream in place. Returns whether it changed."""
    if turn_has_events(turn):
        return False
    turn["events"] = derive_turn_events(turn)
    return True


def migrate_record(record: ConversationRecord) -> bool:
    """Derive events for every turn that lacks them. Returns whether anything changed.

    Idempotent and version-agnostic: a v7 record passes through untouched, a v5 record
    gains events on every turn. The version itself is stamped by ``_save`` once every
    turn qualifies, so a migrated-in-memory record that is never written keeps saying
    what is actually on disk.
    """
    changed = False
    for turn in record.turns:
        if isinstance(turn, dict) and migrate_turn(turn):
            changed = True
    return changed


def migrate_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Migrate a raw stored ``record_json`` payload; returns it and the turns changed.

    Used by the one-off migration script, which works on rows rather than records so a
    dry run can report without loading every conversation through the owner filter.
    """
    turns = [turn for turn in payload.get("turns", []) if isinstance(turn, dict)]
    changed = sum(1 for turn in turns if migrate_turn(turn))
    migrated = dict(payload)
    migrated["turns"] = turns
    migrated["version"] = RECORD_VERSION
    return migrated, changed


def begin_turn(
    conversation_id: str, user: str, question: str, *, pinned: str | None = None,
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
    record.turns.append({
        "id": turn_id,
        "question": question,
        "pinned": pinned,
        "source_policy": source_policy,
        "route": None,
        "sources": [],  # compatibility with version-1 clients
        "cards": [],
        "agent_exchanges": [],
        "events": [{
            "sequence": 0,
            "type": "user_message",
            "timestamp": created_at.isoformat(),
            "payload": {"role": "user", "content": question},
        }],
        "answer": None,
        "synthesis": None,
        "refusal": None,
        "error": None,
        "error_details": None,
        "status": "running",
        "created_at": created_at.isoformat(),
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
    reason: str = "",
    effective_sources: list[str] | tuple[str, ...] = (),
    tools: list[str] | tuple[str, ...] = (),
) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["sources"] = list(sources)
        turn["route"] = {
            "sources": list(sources), "intent": intent, "model": model,
            "reason": reason,
            "effective_sources": list(effective_sources),
            "tools": list(tools),
        }
        _append_turn_event(turn, "route_decision", dict(turn["route"]))

    _mutate(conversation_id, user, turn_id, apply)


def add_card(conversation_id: str, user: str, turn_id: str, card: dict[str, Any]) -> None:
    """Persist a card produced by the legacy source handlers.

    Legacy sources have no native tool exchange, so the rendered card is the only record
    of what they returned and gets its own ``tool_result`` event. Native results must not
    come through here: their ``tool_result`` event already carries the card, and
    `add_agent_exchange` fills the History rail's ``cards`` view from it.
    """
    def apply(turn: dict[str, Any]) -> None:
        turn.setdefault("cards", []).append(card)
        _append_turn_event(turn, "tool_result", {
            "execution_path": "legacy_or_rendered",
            "card": card,
        })

    _mutate(conversation_id, user, turn_id, apply)


def add_agent_exchange(
    conversation_id: str,
    user: str,
    turn_id: str,
    *,
    assistant_message: ChatMessage,
    calls: list[dict[str, Any]],
    tool_messages: list[ChatMessage],
    stage: str = "route",
    cards: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> None:
    """Persist one complete native exchange; never leave calls without tool results.

    ``stage`` names the request the assistant message answered (``route`` for the
    selection request, ``continue`` for a later tool round). ``cards`` are the rendered
    views the client was streamed for this round; they are kept on the turn for the
    History rail in the same write as the events, and get no event of their own because
    the ``tool_result`` events already carry the complete results.
    """
    if len(calls) != len(tool_messages):
        raise ValueError("every persisted native call needs one tool result")
    call_ids = [str(call.get("id", "")) for call in calls]
    result_ids = [str(message.get("tool_call_id", "")) for message in tool_messages]
    assistant_ids = [
        str(call.get("id", ""))
        for call in assistant_message.get("tool_calls", [])
        if isinstance(call, dict)
    ]
    if not all(call_ids) or call_ids != result_ids or call_ids != assistant_ids:
        raise ValueError("native call IDs must match assistant and tool-result messages")
    safe_calls = [_sanitize_agent_call(call) for call in calls]
    safe_assistant = _sanitize_assistant_tool_calls(assistant_message)
    safe_tools = [dict(message) for message in tool_messages]
    rendered = [dict(card) for card in cards if isinstance(card, dict)]

    def apply(turn: dict[str, Any]) -> None:
        if settings.workbench_history_write_legacy_exchanges:
            turn.setdefault("agent_exchanges", []).append({
                "assistant": safe_assistant,
                "calls": safe_calls,
                "tools": safe_tools,
            })
        _append_native_exchange_events(
            turn, assistant=safe_assistant, calls=safe_calls, tool_messages=safe_tools,
            stage=stage,
        )
        if rendered:
            turn.setdefault("cards", []).extend(rendered)

    _mutate(conversation_id, user, turn_id, apply)


def add_system_message(
    conversation_id: str, user: str, turn_id: str, *, content: str, kind: str,
    stage: str = "", round_number: int = 0,
) -> None:
    """Record a message the application injected into the model's context.

    Nudges and similar synthetic user messages are stored so the event stream is the
    exact transcript the model saw; whether they are ever resent is a replay decision
    (`REPLAYED_SYSTEM_MESSAGE_KINDS`), not a storage one.
    """
    def apply(turn: dict[str, Any]) -> None:
        _append_turn_event(turn, "system_message", {
            "execution_path": "native",
            "kind": kind,
            "stage": stage,
            "round": int(round_number),
            "synthetic": True,
            "message": {"role": "user", "content": content},
        })

    _mutate(conversation_id, user, turn_id, apply)


def _sanitize_agent_call(call: dict[str, Any]) -> dict[str, Any]:
    safe = dict(call)
    if safe.get("name") == "search_public_web":
        arguments = safe.get("arguments") if isinstance(safe.get("arguments"), dict) else {}
        query = str(arguments.get("search_query", ""))
        safe["arguments"] = {
            "search_query": "[redacted after policy evaluation]",
            "query_hash": hashlib.sha256(query.encode()).hexdigest() if query else "",
        }
    return safe


def _sanitize_assistant_tool_calls(message: ChatMessage) -> ChatMessage:
    safe: ChatMessage = {
        "role": "assistant",
        "content": message.get("content"),
    }
    if "reasoning_content" in message:
        safe["reasoning_content"] = message.get("reasoning_content") or ""
    sanitized = []
    for raw in message.get("tool_calls", []) or []:
        if not isinstance(raw, dict):
            continue
        call = dict(raw)
        function = dict(call.get("function") or {})
        if function.get("name") == "search_public_web":
            function["arguments"] = json.dumps({
                "search_query": "[redacted after policy evaluation]",
            }, separators=(",", ":"))
        call["function"] = function
        sanitized.append(call)
    if sanitized:
        safe["tool_calls"] = sanitized
    return safe


def set_synthesis(
    conversation_id: str, user: str, turn_id: str, text: str, *,
    message: ChatMessage | None = None, stage: str = "synthesize",
) -> None:
    """Record what the model wrote before grounding and repair touched it.

    This is the candidate, not the answer: `set_answer` records the text the user was
    shown, which may be a repaired or extractive replacement. When the two are the same
    text the record still holds one model output and one user-facing answer, not the
    same event twice.
    """
    stored: ChatMessage = (
        _sanitize_assistant_tool_calls(message) if isinstance(message, dict)
        else {"role": "assistant", "content": text}
    )

    def apply(turn: dict[str, Any]) -> None:
        turn["synthesis"] = text
        _append_turn_event(turn, "llm_assistant_message", {
            "execution_path": "synthesis",
            "stage": stage,
            "candidate": True,
            "message": stored,
        })

    _mutate(conversation_id, user, turn_id, apply)


def set_answer(
    conversation_id: str, user: str, turn_id: str, payload: dict[str, Any]
) -> None:
    """Persist the one user-facing answer while keeping `synthesis` for old clients."""
    def apply(turn: dict[str, Any]) -> None:
        turn["answer"] = payload
        turn["synthesis"] = str(payload.get("text", "")) or None
        _append_turn_event(turn, "final_answer", {"answer": payload})

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
                prompt_tokens if total_prompt_tokens is None else total_prompt_tokens
            ),
            "cached_prompt_tokens": int(cached_prompt_tokens),
            "cache_write_prompt_tokens": int(cache_write_prompt_tokens),
            "uncached_prompt_tokens": int(
                max(0, prompt_tokens - cached_prompt_tokens)
                if uncached_prompt_tokens is None else uncached_prompt_tokens
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
    conversation_id: str, user: str, turn_id: str, *,
    first_event_ms: int = 0, first_card_ms: int = 0, final_answer_ms: int = 0,
    total_ms: int = 0, source_attempts: list[str] | None = None,
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


def set_refusal(conversation_id: str, user: str, turn_id: str, payload: dict[str, Any]) -> None:
    def apply(turn: dict[str, Any]) -> None:
        turn["refusal"] = payload
        _append_turn_event(turn, "final_answer", {"refusal": payload})

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
        _append_turn_event(turn, "execution_error", details)

    _mutate(conversation_id, user, turn_id, apply)


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


def private_entities(conversation_id: str, *, user: str) -> tuple[str, ...]:
    """Return exact previously selected private entity values for outbound screening."""
    record = _load(conversation_id, user)
    if record is None:
        return ()
    values: list[str] = []
    for turn in record.turns:
        for call in native_tool_calls(turn):
            arguments = call.get("arguments")
            if not isinstance(arguments, dict):
                continue
            if call.get("name") == "lookup_records":  # version-7 history compatibility
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
                    if literal.is_string and len(str(literal.this).strip()) >= 2
                )
            except Exception:  # noqa: BLE001 - malformed historical SQL contributes no entities
                logger.debug("could not extract private literals from historical MCP SQL")
    return tuple(dict.fromkeys(values[-20:]))


def native_tool_calls(turn: dict[str, Any]) -> list[dict[str, Any]]:
    """Every native tool call of a turn, in execution order, read from its events."""
    calls: list[dict[str, Any]] = []
    for event in turn_events(turn):
        payload = event.get("payload")
        if event.get("type") != "tool_call" or not isinstance(payload, dict):
            continue
        call = payload.get("call")
        if isinstance(call, dict):
            calls.append(call)
    return calls


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


def _tool_names_in(assistant_message: dict[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for call in assistant_message.get("tool_calls") or []:
        if isinstance(call, dict):
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            names[str(call.get("id", ""))] = str(function.get("name", ""))
    return names


def _observation(tool_message: dict[str, Any], tool_names: dict[str, str]) -> ChatMessage:
    """Replay a stored tool result bounded the same way a live observation is."""
    from app.services.workbench.agent_executor import shape_observation_text

    message = dict(tool_message)
    content = message.get("content")
    if isinstance(content, str):
        message["content"] = shape_observation_text(
            content, tool_name=tool_names.get(str(message.get("tool_call_id", ""))) or None,
        )
    return message


def native_replay_group(turn: dict[str, Any]) -> list[ChatMessage]:
    """What one turn contributes to the provider transcript, read from its events.

    The question, every native assistant message with the bounded observation of each
    of its tool results, any stored system message the replay policy admits, and the
    final assistant text. Empty when the turn has no question. This is the one place the
    replay shape is defined: `build_native_transcript` sends it and the compaction
    trigger measures it.
    """
    question = str(turn.get("question", "")).strip()
    if not question:
        return []
    group: list[ChatMessage] = [{"role": "user", "content": question}]
    tool_names: dict[str, str] = {}
    for event in turn_events(turn):
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("execution_path") != "native":
            continue
        kind = event.get("type")
        message = payload.get("message")
        if not isinstance(message, dict):
            continue
        if kind == "llm_assistant_message":
            tool_names.update(_tool_names_in(message))
            group.append(dict(message))
        elif kind == "tool_result":
            group.append(_observation(message, tool_names))
        elif kind == "system_message" and payload.get("kind") in REPLAYED_SYSTEM_MESSAGE_KINDS:
            group.append(dict(message))
    answer = _assistant_text(turn)
    if answer:
        group.append({"role": "assistant", "content": answer})
    return group


def replay_group_tokens(group: list[ChatMessage]) -> int:
    """The estimated cost of one replay group, as the transcript budget counts it."""
    from app.services.workbench.compaction import budget

    if not group:
        return 0
    return budget.estimate_tokens(json.dumps(group, default=str, ensure_ascii=False))


@dataclass(slots=True)
class NativeReplayMeasure:
    """How large the native replay of a conversation would be, before any budget cut.

    ``tokens`` follows the budget module's rule: trust the provider where it has spoken,
    estimate only what came after. When a live turn carries a measured prompt size that
    postdates the checkpoint, that measurement anchors the count and only that turn's
    completion and the turns after it are estimated; otherwise every live turn's replay
    group is estimated as `build_native_transcript` would send it.
    """

    tokens: int = 0
    summary_tokens: int = 0
    newest_turn_tokens: int = 0
    measured_turn_id: str = ""
    turn_ids: list[str] = field(default_factory=list)


def live_turns(record: ConversationRecord) -> list[dict[str, Any]]:
    """The completed turns replayed verbatim: everything after the checkpoint."""
    complete = [turn for turn in record.turns if turn.get("status") != "running"]
    compaction = record.compaction if isinstance(record.compaction, dict) else None
    first_kept = str(compaction.get("first_kept_turn_id", "")) if compaction else ""
    _, live = _split_at_turn(complete, first_kept)
    return live


def _measured_after(turn: dict[str, Any], checkpoint_created_at: str) -> bool:
    """Whether a turn's measured prompt saw the current checkpoint rather than the
    verbatim turns it later replaced. Timestamps are UTC ISO-8601, so they order
    lexically; a turn without one is treated as older than any checkpoint."""
    if not checkpoint_created_at:
        return True
    completed_at = str(turn.get("completed_at") or "")
    return bool(completed_at) and completed_at >= checkpoint_created_at


def measure_replay_turns(
    turns: list[dict[str, Any]], *, checkpoint_created_at: str = "",
) -> NativeReplayMeasure:
    """Measure the native replay of these turns (running turns skipped)."""
    from app.services.workbench.compaction import budget

    measure = NativeReplayMeasure()
    complete = [turn for turn in turns if turn.get("status") != "running"]
    anchor = -1
    for index in range(len(complete) - 1, -1, -1):
        if (
            budget.measured_prompt_tokens(complete[index]) is not None
            and _measured_after(complete[index], checkpoint_created_at)
        ):
            anchor = index
            break
    for index, turn in enumerate(complete):
        group = native_replay_group(turn)
        if not group:
            continue
        cost = replay_group_tokens(group)
        measure.newest_turn_tokens = cost
        measure.turn_ids.append(str(turn.get("id", "")))
        if index < anchor:
            continue
        if index == anchor:
            # The measured prompt covers everything up to this turn's last request; its
            # final text was the completion and is only in the *next* transcript.
            measure.measured_turn_id = str(turn.get("id", ""))
            measure.tokens += int(budget.measured_prompt_tokens(turn) or 0)
            measure.tokens += budget.estimate_tokens(_assistant_text(turn))
            continue
        measure.tokens += cost
    return measure


def measure_native_replay(record: ConversationRecord) -> NativeReplayMeasure:
    """Measure what `build_native_transcript` would send for this record."""
    from app.services.workbench.compaction import budget

    compaction = record.compaction if isinstance(record.compaction, dict) else None
    created_at = str(compaction.get("created_at", "")) if compaction else ""
    measure = measure_replay_turns(live_turns(record), checkpoint_created_at=created_at)
    summary = str(compaction.get("summary", "")).strip() if compaction else ""
    if summary:
        limit = budget.budget_tokens()
        summary = budget.clip_to_tokens(summary, int(limit * budget.SUMMARY_SHARE))
        measure.summary_tokens = budget.estimate_tokens(summary)
        if not measure.measured_turn_id:
            # A measured prompt taken after the checkpoint already contained it.
            measure.tokens += measure.summary_tokens
    return measure


def build_native_transcript(
    conversation_id: str,
    *,
    user: str,
    token_budget: int | None = None,
) -> list[ChatMessage]:
    """Replay complete native exchanges or fail rather than silently clipping them."""
    from app.services.workbench.compaction import budget

    limit = budget.budget_tokens() if token_budget is None else token_budget
    record = _load(conversation_id, user)
    if record is None:
        return []
    messages: list[ChatMessage] = []
    spent = 0
    compaction = record.compaction if isinstance(record.compaction, dict) else None
    summary = str(compaction.get("summary", "")).strip() if compaction else ""
    if summary:
        summary = budget.clip_to_tokens(summary, int(limit * budget.SUMMARY_SHARE))
        messages.append({"role": "system", "content": "Conversation checkpoint:\n\n" + summary})
        spent += budget.estimate_tokens(summary)

    groups = [group for turn in live_turns(record) if (group := native_replay_group(turn))]
    kept: list[list[ChatMessage]] = []
    for group in reversed(groups):
        cost = replay_group_tokens(group)
        if spent + cost > limit:
            if not kept:
                # The newest turn does not fit even on its own. Compaction summarizes
                # older turns and cannot shrink this one; only a new conversation helps.
                raise NativeTranscriptOverflow(
                    "the most recent turn alone exceeds the context window; "
                    "start a new conversation",
                    reason="single_turn_exceeds_budget",
                )
            raise NativeTranscriptOverflow(
                "complete native conversation exceeds the context window; "
                "start a new conversation or enable explicit compaction",
                reason="conversation_exceeds_budget",
            )
        kept.append(group)
        spent += cost
    messages.extend(message for group in reversed(kept) for message in group)
    return messages


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
    answer = turn.get("answer")
    if isinstance(answer, dict) and answer.get("text"):
        # The final answer already combines the source findings. Replaying source cards as
        # additional assistant prose duplicates facts and biases follow-up synthesis.
        return str(answer["text"])
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
    if card_type == "briefing":
        # The headline and the signals. The analyses underneath are already summarised by
        # their own headlines, and copying every chart row of a five-section briefing into
        # model context spends the whole budget on one turn.
        headline = str(payload.get("headline") or "")
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        analyses = payload.get("analyses") if isinstance(payload.get("analyses"), list) else []
        lines = [f"- {s.get('text')}" for s in signals if isinstance(s, dict) and s.get("text")]
        lines += [
            f"- {a.get('title')}: {a.get('headline')}"
            for a in analyses
            if isinstance(a, dict) and a.get("headline")
        ]
        return "\n".join(
            part for part in [f"[{source}] {payload.get('label', 'Briefing')}", headline, *lines]
            if part
        )
    if card_type == "worklist":
        # The top of the list and the shape of the rest. A worklist can run to fifty named
        # borrowers, and copying all of them into model context spends the budget on PII to
        # no benefit — the follow-up questions are about the pattern, not the roster.
        title = str(payload.get("title") or "Worklist")
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        head = [
            f"- #{item.get('rank')} {item.get('account')} ({item.get('severity')}): "
            + " ".join(str(r) for r in (item.get("reasons") or []))
            for item in items[:5]
            if isinstance(item, dict)
        ]
        rest = len(items) - len(head)
        lines = [f"[{source}] {title}: {len(items)} accounts", *head]
        if rest > 0:
            lines.append(f"[{rest} further accounts omitted from model context]")
        return "\n".join(lines)
    if card_type == "brief":
        summary = str(payload.get("summary") or "")
        points = payload.get("key_points") if isinstance(payload.get("key_points"), list) else []
        return "\n".join([f"[{source}] {summary}", *(f"- {point}" for point in points)])
    if card_type == "schema":
        return f"[{source}] Schema: {payload.get('node_count', 0)} tables, {payload.get('edge_count', 0)} relationships."
    return str(payload.get("message") or payload.get("question") or "")
