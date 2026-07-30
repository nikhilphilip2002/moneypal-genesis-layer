"""Multi-turn context: "…and by branch?" / "same for gold loans".

Two design points carry most of the value.

**Structural follow-ups skip the LLM entirely.** A follow-up that only adds a dimension or
changes a filter is detected by pattern, applied to the anchor spec, and recompiled. That
is instant, free and always correct — no model call can get it wrong.

**Sticky filters are visible.** Invisible carried-over state is the single largest source
of confusion in conversational analytics: the user asks about gold loans, then asks a
general question, and quietly gets a gold-only answer. Every sticky filter is returned to
the UI as a dismissible chip, and the anchor resets when the subject changes.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import ConversationState, QuerySpec, Turn

logger = logging.getLogger(__name__)

IDLE_EXPIRY = timedelta(minutes=30)
MAX_TURNS = 5
TABLE = "public.nlq_conversations"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    conversation_id text PRIMARY KEY,
    state_json      jsonb NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
"""

_memory: dict[str, ConversationState] = {}
_lock = threading.Lock()
_table_ready = False

# A follow-up is recognised by shape, not by asking a model. These patterns are
# deliberately conservative: a false positive silently answers the wrong question, so
# anything not clearly elliptical goes down the normal planning path.
_ADD_DIMENSION = re.compile(
    r"^(?:and|also|now|ok)?\s*(?:show|split|break(?:\s*it)?\s*down|group)?\s*"
    r"(?:me\s+)?(?:it\s+)?by\s+(?P<dimension>[a-z_ ]+)\??$",
    re.IGNORECASE,
)
_SAME_FOR = re.compile(
    r"^(?:and\s+)?(?:the\s+)?same\s+(?:for|with)\s+(?P<value>.+?)\??$", re.IGNORECASE
)
_WHAT_ABOUT = re.compile(
    r"^(?:and\s+)?what\s+about\s+(?P<value>.+?)\??$", re.IGNORECASE
)


# --------------------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------------------


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
        logger.warning("NLQ conversation table unavailable, using memory: %s", exc)
        return False


def load(conversation_id: str) -> ConversationState:
    """Fetch state, or a fresh one. Expired context is discarded rather than resumed."""
    with _lock:
        state = _memory.get(conversation_id)
    if state is None and _ensure_table():
        state = _load_from_db(conversation_id)

    if state is None:
        return ConversationState(conversation_id=conversation_id)

    if state.updated_at and _now() - state.updated_at > IDLE_EXPIRY:
        logger.info("NLQ conversation %s expired after idle timeout", conversation_id)
        return ConversationState(conversation_id=conversation_id)
    return state


def _load_from_db(conversation_id: str) -> ConversationState | None:
    try:
        from app.services.db_schema import db_cursor

        with db_cursor() as (conn, cur):
            cur.execute(
                f"SELECT state_json FROM {TABLE} WHERE conversation_id = %s", (conversation_id,)
            )
            row = cur.fetchone()
            conn.rollback()
        if not row:
            return None
        payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return ConversationState.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ conversation load failed for %s: %s", conversation_id, exc)
        return None


def save(state: ConversationState) -> None:
    """Persist to Postgres so context survives a backend restart; memory is the fallback."""
    state.updated_at = _now()
    with _lock:
        _memory[state.conversation_id] = state

    if not _ensure_table():
        return
    try:
        from app.services.db_schema import db_cursor

        payload = state.model_dump(mode="json")
        with db_cursor() as (conn, cur):
            cur.execute(
                f"INSERT INTO {TABLE} (conversation_id, state_json, updated_at) "
                "VALUES (%s, %s, now()) ON CONFLICT (conversation_id) DO UPDATE "
                "SET state_json = EXCLUDED.state_json, updated_at = now()",
                (state.conversation_id, json.dumps(payload, default=str)),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ conversation save failed for %s: %s", state.conversation_id, exc)


def clear(conversation_id: str) -> None:
    with _lock:
        _memory.pop(conversation_id, None)
    if _ensure_table():
        try:
            from app.services.db_schema import db_cursor

            with db_cursor() as (conn, cur):
                cur.execute(f"DELETE FROM {TABLE} WHERE conversation_id = %s", (conversation_id,))
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("NLQ conversation clear failed: %s", exc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------------------
# State mutation
# --------------------------------------------------------------------------------------


def append_turn(
    state: ConversationState,
    question: str,
    resolved: str,
    route: str,
    chart_type: str | None,
    row_count: int,
) -> None:
    state.turns.append(
        Turn(
            question=question,
            resolved_question=resolved,
            route=route,  # type: ignore[arg-type]
            chart_type=chart_type,  # type: ignore[arg-type]
            row_count=row_count,
            ts=_now(),
        )
    )
    del state.turns[:-MAX_TURNS]


def set_anchor(state: ConversationState, spec: QuerySpec) -> None:
    """The anchor is what a follow-up mutates. Sticky filters are surfaced to the UI."""
    state.active_spec = spec
    state.entities = {
        f.field: str(f.value) for f in spec.filters if f.op == "eq" and f.value is not None
    }


def sticky_filters(state: ConversationState, catalog: Catalog | None = None) -> list[dict[str, str]]:
    """Dismissible chips for the UI — carried-over state must always be visible."""
    cat = catalog or get_catalog()
    chips = []
    for field, value in state.entities.items():
        dim = cat.dimensions.get(field)
        enum = cat.enum_for_dimension(dim.decode) if dim and dim.decode else None
        chips.append(
            {
                "field": field,
                "label": dim.label if dim else field,
                "value": value,
                "display": enum.label_for(value) if enum else value,
            }
        )
    return chips


# --------------------------------------------------------------------------------------
# Reference resolution
# --------------------------------------------------------------------------------------


def resolve(
    question: str, state: ConversationState, catalog: Catalog | None = None
) -> tuple[str, QuerySpec | None]:
    """Rewrite a follow-up into a standalone question.

    Returns (resolved_question, structural_spec). A non-None spec means the follow-up was
    handled structurally and no LLM call is needed at all.
    """
    cat = catalog or get_catalog()
    text = question.strip()
    anchor = state.active_spec

    if anchor is None or not text:
        return text, None

    # The structural patterns are checked FIRST. "same for gold loans" contains the word
    # "loans", which lexically matches a metric label and would otherwise be misread as a
    # new subject — losing the follow-up and the anchor with it.
    match = _ADD_DIMENSION.match(text)
    if match:
        dimension = _match_dimension(match.group("dimension"), cat)
        if dimension:
            spec = anchor.model_copy(
                update={"dimensions": _replace_categorical(anchor, dimension, cat)}
            )
            return f"{_describe(anchor, cat)} by {cat.dimensions[dimension].label.lower()}", spec

    for pattern in (_SAME_FOR, _WHAT_ABOUT):
        match = pattern.match(text)
        if not match:
            continue
        filters = _match_filter_value(match.group("value"), cat)
        if filters:
            field, code, label = filters
            kept = [f for f in anchor.filters if f.field != field]
            from app.services.nlq.contracts import Filter

            spec = anchor.model_copy(
                update={"filters": [*kept, Filter(field=field, op="eq", value=code)]}
            )
            return f"{_describe(anchor, cat)} for {label}", spec

    # No structural match. A question that names its own metric is a new subject and must
    # not inherit the anchor's filters.
    if _is_new_subject(text, cat):
        return text, None

    # Elliptical but not structurally recognised: hand the planner a complete question
    # rather than the fragment, so retrieval and the audit log both see the real intent.
    if _looks_elliptical(text):
        return f"{_describe(anchor, cat)}; {text}", None

    return text, None


def _is_new_subject(text: str, catalog: Catalog) -> bool:
    """A question naming its own metric resets the anchor — otherwise a fresh question
    silently inherits the previous one's filters."""
    if len(text.split()) < 4:
        return False
    return bool(catalog.search_metrics(text))


def _looks_elliptical(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered.startswith(("and ", "what about", "same ", "also ", "how about")):
        return True
    return len(lowered.split()) <= 4 and not lowered.startswith(("what is", "show", "how many"))


def _match_dimension(text: str, catalog: Catalog) -> str | None:
    needle = text.strip().lower().rstrip("?").strip()
    for dim in catalog.dimensions.values():
        if needle == dim.id or needle == dim.label.lower():
            return dim.id
        if any(needle == s.lower() for s in dim.synonyms):
            return dim.id
    for dim in catalog.dimensions.values():
        if needle and needle in dim.label.lower():
            return dim.id
    return None


def _match_filter_value(text: str, catalog: Catalog) -> tuple[str, str, str] | None:
    """Resolve "gold loans" to (dimension, code, label). Exact matches only."""
    needle = text.strip().lower().rstrip("?").strip()
    for dim in catalog.dimensions.values():
        if dim.is_time or not dim.decode:
            continue
        block = catalog.enum_for_dimension(dim.decode)
        if block is None:
            continue
        code = block.code_for(needle)
        if code is not None:
            return dim.id, code, block.values[code].label
    return None


def _replace_categorical(spec: QuerySpec, dimension: str, catalog: Catalog) -> list[str]:
    """"and by branch?" replaces the previous categorical split rather than stacking on it —
    stacking produces a two-dimensional heatmap nobody asked for."""
    if catalog.dimensions[dimension].is_time:
        return [*[d for d in spec.dimensions if not catalog.dimensions[d].is_time], dimension]
    kept = [d for d in spec.dimensions if catalog.dimensions[d].is_time]
    return [*kept, dimension]


def _describe(spec: QuerySpec, catalog: Catalog) -> str:
    metrics = " and ".join(catalog.metrics[m].label.lower() for m in spec.metrics)
    period = spec.period.relative or (
        f"{spec.period.start} to {spec.period.end}" if spec.period.start else "all time"
    )
    return f"{metrics} for {str(period).replace('_', ' ')}"
