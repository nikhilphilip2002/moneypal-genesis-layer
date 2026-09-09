"""Session state extracted mechanically from completed turns — no LLM involved.

This is the workbench's answer to the file-path tracking in the pi coding agent. pi
scans tool calls for the paths it must not lose; we scan completed turns for the
identifiers *we* must not lose. The motivating difference is stakes: if a coding agent's
summary forgets a path, it re-reads the file. If ours rounds "MSME credit grew 6.5%" to
"about 6%", a wrong figure reaches a bank's briefing.

So figures never travel through a language model. They are parsed out of the structured
card payloads that are already stored on each turn, carried verbatim, and re-derived on
every compaction. Whatever the prose summary says or forgets, this block is exact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services import figures as figure_parser

MAX_FIGURES = 40
MAX_FIGURES_PER_TURN = 6
# Refusals need a cap for the same reason figures do: this block ships on every request,
# and a conversation that repeatedly hits role-based denials would otherwise accumulate
# one line per denial forever.
MAX_REFUSALS = 8
MAX_METRICS = 30
MAX_ANCHORS = 20
SENTENCE_MAX = 160


@dataclass(slots=True, frozen=True)
class Figure:
    label: str
    value: str
    period: str
    source: str
    turn_id: str

    def render(self) -> str:
        return f"{self.label} | {self.value} | {self.period or '—'} | {self.source} | {self.turn_id}"


@dataclass(slots=True)
class SessionState:
    figures: list[Figure] = field(default_factory=list)
    sources_consulted: set[str] = field(default_factory=set)
    metrics_seen: set[str] = field(default_factory=set)
    refusals: list[str] = field(default_factory=list)
    pinned: str | None = None
    active_plans: list[str] = field(default_factory=list)
    selected_entities: list[str] = field(default_factory=list)
    ranked_rows: list[str] = field(default_factory=list)
    fact_references: list[str] = field(default_factory=list)
    drill_actions: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.figures or self.sources_consulted or self.metrics_seen or self.refusals
            or self.pinned or self.active_plans or self.selected_entities
            or self.ranked_rows or self.fact_references or self.drill_actions
        )


def _clean(text: str) -> str:
    return " ".join(str(text).split())


def _period_in(text: str) -> str:
    return figure_parser.find_period(text)


def _values_in(text: str) -> list[str]:
    """Pull the quantities out of a line, preserving how they were written."""
    return [quantity.text for quantity in figure_parser.find_quantities(text)]


def _figures_from_text(
    text: str, *, source: str, turn_id: str, fallback_period: str
) -> list[Figure]:
    """One row per line, with that line's quantities collected into the value column.

    A line carrying several numbers ("term loans 5.1%, working capital 3.4%") emits one
    row rather than one per number: the sentence is already the context for all of them,
    and repeating it per value triples the size of a block that ships on every request.
    """
    figures: list[Figure] = []
    for raw_line in text.splitlines():
        line = _clean(raw_line)
        if not line:
            continue
        values = _dedupe_values(_values_in(line))
        if not values:
            continue
        figures.append(
            Figure(
                label=line[:SENTENCE_MAX],
                value=", ".join(values),
                period=_period_in(line) or fallback_period,
                source=source,
                turn_id=turn_id,
            )
        )
    return figures


def _dedupe_values(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _chart_state(card: dict[str, Any], payload: dict[str, Any], state: SessionState) -> None:
    columns = payload.get("columns") if isinstance(payload.get("columns"), list) else []
    for column in columns:
        if isinstance(column, dict) and column.get("name"):
            state.metrics_seen.add(str(column["name"]))
    title = _clean(payload.get("title") or "")
    if title:
        state.metrics_seen.add(title)


def extract_turn(turn: dict[str, Any], assistant_text: str) -> SessionState:
    """Everything worth keeping from one completed turn."""
    state = SessionState()
    turn_id = str(turn.get("id", ""))

    route = turn.get("route")
    if isinstance(route, dict):
        for source in route.get("sources") or []:
            state.sources_consulted.add(str(source))

    refusal = turn.get("refusal")
    if isinstance(refusal, dict) and refusal.get("message"):
        state.refusals.append(f"{_clean(refusal['message'])[:SENTENCE_MAX]} ({turn_id})")

    if turn.get("pinned"):
        state.pinned = str(turn["pinned"])

    # Native calls are read from the turn's event stream — the one representation every
    # reader shares — never from the per-turn exchange copy kept for rollback.
    from app.services.workbench.history import native_tool_calls

    for call in native_tool_calls(turn):
        name = str(call.get("name", ""))
        arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        if name in {
            "query_metrics", "run_analysis", "create_worklist",
            "generate_briefing", "run_validated_query",
        }:
            rendered = json.dumps(arguments, sort_keys=True, default=str, separators=(",", ":"))
            state.active_plans.append(f"{name}:{rendered[:600]}")
        if name == "lookup_records":
            selector = str(arguments.get("selector", ""))
            value = str(arguments.get("value", ""))
            if selector and value:
                state.selected_entities.append(f"{selector}={value}"[:SENTENCE_MAX])

    fallback_period = _period_in(str(turn.get("question", "")))
    for card in turn.get("cards") or []:
        if not isinstance(card, dict) or card.get("card_type") != "chart":
            continue
        payload = card.get("payload") if isinstance(card.get("payload"), dict) else {}
        _chart_state(card, payload, state)
        active_plan = payload.get("drilldown")
        if isinstance(active_plan, dict):
            state.active_plans.append(
                "query_metrics:"
                + json.dumps(active_plan, sort_keys=True, default=str, separators=(",", ":"))[:600]
            )
        for action in payload.get("next_steps") or []:
            if not isinstance(action, dict):
                continue
            action_id = str(action.get("id", ""))
            question = str(action.get("question", ""))
            if action_id or question:
                state.drill_actions.append(f"{action_id}:{question}"[:SENTENCE_MAX])
        columns = payload.get("columns") if isinstance(payload.get("columns"), list) else []
        text_fields = [
            str(column.get("name"))
            for column in columns
            if isinstance(column, dict) and column.get("unit") == "text" and column.get("name")
        ]
        numeric_fields = [
            str(column.get("name"))
            for column in columns
            if isinstance(column, dict)
            and column.get("unit") not in {"text", "date", "datetime", "boolean"}
            and column.get("name")
        ]
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        if payload.get("chart_type") == "ranking":
            for rank, row in enumerate(rows[:5], start=1):
                if isinstance(row, dict):
                    identity = ", ".join(
                        f"{field}={row[field]}" for field in text_fields if row.get(field) is not None
                    )
                    if identity:
                        state.ranked_rows.append(f"{rank}:{identity}"[:SENTENCE_MAX])
        for row_index, row in enumerate(rows[:20]):
            if not isinstance(row, dict):
                continue
            for field_name in numeric_fields:
                if row.get(field_name) is not None:
                    state.fact_references.append(
                        f"{turn_id}:{row_index}:{field_name}={row[field_name]}"[:SENTENCE_MAX]
                    )

    # Figures come from the rendered assistant text rather than the raw payload: that is
    # the same view the model was given, already row-capped by history._card_text, so a
    # figure recorded here is one the model genuinely saw.
    figures = _figures_from_text(
        assistant_text,
        source=",".join(sorted(state.sources_consulted)) or "workbench",
        turn_id=turn_id,
        fallback_period=fallback_period,
    )
    state.figures = _dedupe(figures)[:MAX_FIGURES_PER_TURN]
    return state


def _dedupe(figures: Iterable[Figure]) -> list[Figure]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Figure] = []
    for figure in figures:
        key = (figure.label[:60].lower(), figure.value, figure.period)
        if key in seen:
            continue
        seen.add(key)
        unique.append(figure)
    return unique


def merge(base: SessionState, addition: SessionState) -> SessionState:
    """Fold a turn's state into the running state, newest figures winning on overflow."""
    merged = SessionState(
        figures=_dedupe([*base.figures, *addition.figures]),
        sources_consulted=base.sources_consulted | addition.sources_consulted,
        metrics_seen=base.metrics_seen | addition.metrics_seen,
        refusals=list(dict.fromkeys([*base.refusals, *addition.refusals])),
        pinned=addition.pinned or base.pinned,
        active_plans=list(dict.fromkeys([*base.active_plans, *addition.active_plans]))[-MAX_ANCHORS:],
        selected_entities=list(
            dict.fromkeys([*base.selected_entities, *addition.selected_entities])
        )[-MAX_ANCHORS:],
        ranked_rows=list(dict.fromkeys([*base.ranked_rows, *addition.ranked_rows]))[-MAX_ANCHORS:],
        fact_references=list(
            dict.fromkeys([*base.fact_references, *addition.fact_references])
        )[-MAX_FIGURES:],
        drill_actions=list(
            dict.fromkeys([*base.drill_actions, *addition.drill_actions])
        )[-MAX_ANCHORS:],
    )
    # Keep the most recent of each: a later entry supersedes an earlier one on the same
    # subject far more often than the reverse.
    if len(merged.figures) > MAX_FIGURES:
        merged.figures = merged.figures[-MAX_FIGURES:]
    if len(merged.refusals) > MAX_REFUSALS:
        merged.refusals = merged.refusals[-MAX_REFUSALS:]
    return merged


def trim_to_fit(state: SessionState, max_tokens: int, estimate) -> SessionState:
    """Shed the oldest figures until the rendered block fits `max_tokens`.

    The block is added to every transcript ahead of any live turn, so it must not be
    allowed to crowd out the conversation it exists to summarize. Figures go first
    because they are the largest and most redundant part; sources and refusals are small
    and disproportionately useful.
    """
    trimmed = SessionState(
        figures=list(state.figures),
        sources_consulted=set(state.sources_consulted),
        metrics_seen=set(state.metrics_seen),
        refusals=list(state.refusals),
        pinned=state.pinned,
        active_plans=list(state.active_plans),
        selected_entities=list(state.selected_entities),
        ranked_rows=list(state.ranked_rows),
        fact_references=list(state.fact_references),
        drill_actions=list(state.drill_actions),
    )
    while trimmed.figures and estimate(render(trimmed)) > max_tokens:
        trimmed.figures.pop(0)
    if estimate(render(trimmed)) > max_tokens:
        # Even with no figures it does not fit; drop the least useful remaining block.
        trimmed.metrics_seen = set()
    for values in (
        trimmed.fact_references,
        trimmed.ranked_rows,
        trimmed.active_plans,
        trimmed.selected_entities,
        trimmed.drill_actions,
        trimmed.refusals,
    ):
        while values and estimate(render(trimmed)) > max_tokens:
            values.pop(0)
    if estimate(render(trimmed)) > max_tokens:
        trimmed.sources_consulted = set()
    return trimmed


def from_turns(turns: list[dict[str, Any]], assistant_text_of) -> SessionState:
    state = SessionState()
    for turn in turns:
        if turn.get("status") == "running":
            continue
        state = merge(state, extract_turn(turn, assistant_text_of(turn)))
    return state


def render(state: SessionState) -> str:
    """Tagged blocks appended verbatim to the transcript.

    Tagged rather than prose so the model reads them as reference data, and so a later
    compaction can regenerate them wholesale instead of trying to edit prose.
    """
    if state.is_empty():
        return ""
    blocks: list[str] = []
    if state.figures:
        rows = "\n".join(figure.render() for figure in state.figures)
        blocks.append(
            "<established-figures>\n"
            "label | value | period | source | turn\n"
            f"{rows}\n"
            "</established-figures>"
        )
    if state.sources_consulted:
        blocks.append(
            f"<sources-consulted>{', '.join(sorted(state.sources_consulted))}</sources-consulted>"
        )
    if state.metrics_seen:
        metrics = sorted(state.metrics_seen)[:MAX_METRICS]
        blocks.append(f"<metrics-examined>{', '.join(metrics)}</metrics-examined>")
    if state.refusals:
        joined = "\n".join(state.refusals)
        blocks.append(f"<refusals>\n{joined}\n</refusals>")
    if state.pinned:
        blocks.append(f"<pinned-document>{state.pinned}</pinned-document>")
    if state.active_plans:
        blocks.append("<governed-plans>\n" + "\n".join(state.active_plans) + "\n</governed-plans>")
    if state.selected_entities:
        blocks.append(
            "<selected-entities>\n"
            + "\n".join(state.selected_entities)
            + "\n</selected-entities>"
        )
    if state.ranked_rows:
        blocks.append("<ranked-rows>\n" + "\n".join(state.ranked_rows) + "\n</ranked-rows>")
    if state.fact_references:
        blocks.append(
            "<fact-references>\n"
            + "\n".join(state.fact_references)
            + "\n</fact-references>"
        )
    if state.drill_actions:
        blocks.append(
            "<offered-drill-actions>\n"
            + "\n".join(state.drill_actions)
            + "\n</offered-drill-actions>"
        )
    return "\n\n".join(blocks)


def to_payload(state: SessionState) -> dict[str, Any]:
    return {
        "figures": [
            {
                "label": f.label, "value": f.value, "period": f.period,
                "source": f.source, "turn_id": f.turn_id,
            }
            for f in state.figures
        ],
        "sources_consulted": sorted(state.sources_consulted),
        "metrics_seen": sorted(state.metrics_seen),
        "refusals": list(state.refusals),
        "pinned": state.pinned,
        "active_plans": list(state.active_plans),
        "selected_entities": list(state.selected_entities),
        "ranked_rows": list(state.ranked_rows),
        "fact_references": list(state.fact_references),
        "drill_actions": list(state.drill_actions),
    }


def from_payload(payload: dict[str, Any] | None) -> SessionState:
    if not isinstance(payload, dict):
        return SessionState()
    return SessionState(
        figures=[
            Figure(
                label=str(item.get("label", "")), value=str(item.get("value", "")),
                period=str(item.get("period", "")), source=str(item.get("source", "")),
                turn_id=str(item.get("turn_id", "")),
            )
            for item in payload.get("figures", []) or []
            if isinstance(item, dict)
        ],
        sources_consulted=set(payload.get("sources_consulted") or []),
        metrics_seen=set(payload.get("metrics_seen") or []),
        refusals=list(payload.get("refusals") or []),
        pinned=payload.get("pinned"),
        active_plans=list(payload.get("active_plans") or []),
        selected_entities=list(payload.get("selected_entities") or []),
        ranked_rows=list(payload.get("ranked_rows") or []),
        fact_references=list(payload.get("fact_references") or []),
        drill_actions=list(payload.get("drill_actions") or []),
    )
