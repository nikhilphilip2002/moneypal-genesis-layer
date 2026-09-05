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
    r"^(?:and|also|now|ok)?\s*(?:show|split|break(?:\s+(?:it|that|this))?\s*down|group)?\s*"
    r"(?:me\s+)?(?:(?:it|that|this|the\s+result)\s+)?by\s+"
    r"(?P<dimension>[a-z_ ]+?)[?.!]*$",
    re.IGNORECASE,
)
_ADD_TIME_TREND = re.compile(
    r"^(?:and|also|now|ok)?\s*(?:show\s+)?(?:me\s+)?(?:the\s+)?"
    r"(?P<dimension>monthly|quarterly|weekly|daily)\s+trend[?.!]*$",
    re.IGNORECASE,
)
_WHICH = re.compile(
    r"^(?:and\s+|ok\s+|so\s+)?(?:which|what)\s+(?P<dimension>[a-z_ ]+?)\s*\??$",
    re.IGNORECASE,
)
"""«which branches?» — the same operation as «by branch», in the words people actually use
mid-drill. Anchored to the end of the string, so a full question that merely starts with
"which branches..." carries extra words, matches no dimension, and falls through to the
planner where it belongs."""

_WHY = re.compile(
    r"^(?:and\s+|but\s+|ok\s+)?why"
    r"(?:\s+(?:is|was|are|were|did|does|do)?\s*(?:that|this|it|they|so|the\s+\w+)?)?"
    r"(?:\s+(?:change|changed|move|moved|fall|fell|drop|dropped|rise|rose))?\s*\??$",
    re.IGNORECASE,
)
"""Only the bare forms. "Why did collections fall in Q2?" is a complete question with its
own subject and must be planned; folding it onto the anchor would answer about the anchor's
metric instead of the one the user just named."""

_ACTION = re.compile(
    r"^(?:and\s+|so\s+|ok\s+)?(?:what|who)\s+"
    r"(?:should|do|can)\s+(?:we|i)\s+"
    r"(?:do|action|chase|call|collect|work)"
    r"(?:\s+(?:about|with|on)\s+(?:that|this|it|them|these|those))?\s*\??$",
    re.IGNORECASE,
)
"""«what should we do?» — the last rung of the chain, and the one the whole product is for.

Rewritten into words rather than executed structurally, because the answer is a worklist and
this function's structural shortcut returns a QuerySpec. The rewrite carries the anchor's
filters into the question, so "what should we do?" asked under a chart of Aluva's arrears
produces Aluva's collection list rather than the whole bank's."""

_PRIORITY_LIST = re.compile(
    r"^(?:and\s+|ok\s+)?(?:create|make|build|give|show|get)?\s*(?:me\s+)?(?:the\s+)?"
    r"(?:today'?s?\s+)?(?:collection|collections|priority|call|chase)\s+"
    r"(?:priority\s+)?(?:list|worklist)\s*\??$",
    re.IGNORECASE,
)
"""«create today's collection priority list» — same treatment, said outright."""

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

    # "Why?" is the most common follow-up a director asks and the one that used to be lost
    # entirely — it matched no pattern, named no metric, and reached the planner as a
    # one-word question. It now resolves to the drill graph's decomposition step.
    if _WHY.match(text):
        step = _drill_step(anchor, cat, "explain")
        if step is not None:
            return step.question, step.spec

    # "What should we do?" ends the chain in a worklist rather than another chart. The
    # rewrite names the list outright and carries the anchor's slice into the words, so the
    # planner has nothing left to guess and the list matches the card that prompted it.
    if _ACTION.match(text) or _PRIORITY_LIST.match(text):
        return _worklist_question(anchor, cat), None

    # The structural patterns are checked FIRST. "same for gold loans" contains the word
    # "loans", which lexically matches a metric label and would otherwise be misread as a
    # new subject — losing the follow-up and the anchor with it.
    for pattern in (_ADD_DIMENSION, _ADD_TIME_TREND, _WHICH):
        match = pattern.match(text)
        if not match:
            continue
        base = _without_explanation(anchor, cat)
        dimension = _match_dimension(match.group("dimension"), cat, anchor=base)
        if dimension:
            spec = base.model_copy(
                update={"dimensions": _replace_categorical(base, dimension, cat)}
            )
            return f"{_describe(base, cat)} by {cat.dimensions[dimension].label.lower()}", spec


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


def _without_explanation(spec: QuerySpec, catalog: Catalog) -> QuerySpec:
    """Strip a decomposition back to the plain question underneath it.

    After "why?", the anchor is an explanation: it carries `explain`, a `compare_to`, and —
    for a ratio — the denominator metric that makes the mix/rate split exact. Re-splitting
    from there ("which accounts?") must not inherit any of that, or a request for a list of
    fifty accounts renders as a fifty-bar waterfall of a change nobody asked about.

    Asking "why?" again at the new level is one tap, and that is the predictable behaviour.
    """
    if not spec.explain:
        return spec
    metrics = spec.metrics
    subject = catalog.metrics.get(metrics[0])
    # Drop the weight only if it is exactly the companion this module's explain step added.
    if subject and len(metrics) == 2 and metrics[1] == subject.weight_metric:
        metrics = metrics[:1]
    return spec.model_copy(
        update={"metrics": metrics, "explain": False, "compare_to": None}
    )


def _drill_step(anchor: QuerySpec, catalog: Catalog, kind: str):
    """One offered next step from the drill graph, by kind. Imported late because the drill
    engine reads the catalog this module also serves."""
    from app.services.nlq import drilldown

    steps = drilldown.next_steps(anchor, catalog, limit=len(catalog.dimensions))
    return next((s for s in steps if s.kind == kind), None)


def _worklist_question(anchor: QuerySpec, catalog: Catalog) -> str:
    """"What should we do?" as a question the planner can route without guessing.

    Only the filters a worklist can honour are carried over. A period is deliberately not:
    a collection list is about the book as it stands this morning, and inheriting "last
    quarter" from the chart above would produce a list of accounts whose arrears may have
    been cleared since.
    """
    from app.services.worklists.rules import FILTERABLE

    parts = []
    for filt in anchor.filters:
        dimension = catalog.dimensions.get(filt.field)
        if dimension is None or filt.field not in FILTERABLE or filt.op != "eq":
            continue
        enum = catalog.enum_for_dimension(dimension.decode) if dimension.decode else None
        value = enum.label_for(filt.value) if enum else str(filt.value)
        parts.append(f"{dimension.label.lower()} {value}")

    scope = (" for " + " and ".join(parts)) if parts else ""
    return f"today's collection priority list{scope}"


def _match_dimension(
    text: str, catalog: Catalog, *, anchor: QuerySpec | None = None,
) -> str | None:
    needle = text.strip().lower().rstrip("?").strip()
    # People drill in the plural — "which branches?", "which accounts?" — while the catalog
    # names dimensions in the singular.
    candidates = [needle]
    if needle.endswith("es") and len(needle) > 4:
        candidates.append(needle[:-2])
    if needle.endswith("s") and len(needle) > 3:
        candidates.append(needle[:-1])

    scored: list[tuple[int, str]] = []
    for candidate in candidates:
        for dim in catalog.dimensions.values():
            if candidate == dim.id or candidate == dim.label.lower():
                scored.append((2, dim.id))
            elif any(candidate == s.lower() for s in dim.synonyms):
                scored.append((2, dim.id))
            elif candidate and (
                candidate in dim.label.lower()
                or (
                    dim.label.lower() in candidate
                    and len(candidate.split()) <= 3
                )
            ):
                scored.append((1, dim.id))
    scored = list(dict.fromkeys(scored))
    if anchor is None:
        return max(scored, default=(0, None))[1]

    metric = catalog.metrics.get(anchor.metrics[0])
    if metric is None:
        return None
    compatible = [
        item
        for item in scored
        if catalog.dimensions[item[1]].is_time
        or catalog.dimensions[item[1]].table == metric.base_table
        or catalog.join_between(metric.base_table, catalog.dimensions[item[1]].table) is not None
    ]
    return max(compatible, default=(0, None))[1]


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
