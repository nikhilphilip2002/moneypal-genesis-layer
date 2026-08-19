"""Typed contracts shared by every stage of the NLQ pipeline.

These are the interface between the planner (LLM), the compiler (deterministic), the
executor, the chart builder and the frontend. Nothing here touches a database or an LLM,
so it stays importable from tests with no infrastructure.

`QuerySpec` is the load-bearing type: it is what the LLM emits, what `/nlq/execute`
accepts without any LLM involvement, and what a saved question or a drill-down persists.
That is what keeps the product working when the model is offline.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------

FilterOp = Literal[
    "eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "between", "contains", "is_null"
]
"""Operators the compiler knows how to bind. Anything else is a catalog/planner bug."""

Grain = Literal["day", "week", "month", "quarter", "fy", "year", "all"]

RelativePeriod = Literal[
    "today",
    "yesterday",
    "this_month",
    "last_month",
    "this_quarter",
    "last_quarter",
    "this_fy",
    "last_fy",
    "fy_to_date",
    "ytd",
    "last_12_months",
    "last_30_days",
    "last_90_days",
    "all_time",
]
"""Resolved to concrete dates by the fiscal-calendar module (Indian FY: Apr 1 - Mar 31).

Deliberately a closed set: an open-ended string would let the LLM invent periods the
compiler cannot honour, and "last year" is ambiguous enough here to be a `clarify`."""

Unit = Literal[
    "inr", "percent", "count", "days", "months", "years", "year", "ratio",
    "text", "date", "datetime", "boolean",
]

Sensitivity = Literal["public", "internal", "pii"]

MetricGrain = Literal["flow", "point_in_time", "ratio"]
"""`flow` sums across periods (disbursement). `point_in_time` must not be summed across
dates (PAR, outstanding balance) - it needs a pinned as-of date. `ratio` is recomputed
from numerator/denominator at the requested grain, never averaged from sub-totals."""

ChartType = Literal[
    "kpi",
    "line",
    "area",
    "stacked_area",
    "bar",
    "grouped_bar",
    "stacked_bar",
    "table",
    "ranking",
    "donut",
    "variance",
    "dumbbell",
    "scatter",
    "heatmap",
    "small_multiples",
    "waterfall",
]
"""Every form the renderer knows. The backend picks one deterministically from the result's
shape, so the same question always looks the same — the model never chooses a chart.

`waterfall` renders one thing only: a driver decomposition — prior total, each member's
contribution, current total. It was previously excluded on the grounds that no question in
this catalog called for it, which stopped being true when "why did it change?" became an
answerable question rather than a refusal.

Absent on purpose: any dual-axis form (two y-scales on one plot is the single most
misleading chart there is — mixed units fall back to a table instead), and treemap, radar
and sankey, which still have no question behind them."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# --------------------------------------------------------------------------------------
# Query specification
# --------------------------------------------------------------------------------------


class Filter(_Model):
    field: str = Field(description="Dimension id; must exist in the catalog.")
    op: FilterOp
    value: str | float | int | bool | list[str | float | int] | None = None

    @model_validator(mode="after")
    def _check_value_arity(self) -> "Filter":
        if self.op == "is_null":
            return self  # value is meaningless and ignored
        if self.value is None:
            raise ValueError(f"filter on {self.field!r} with op {self.op!r} needs a value")
        if self.op in ("in", "not_in"):
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"{self.op!r} on {self.field!r} needs a non-empty list")
        elif self.op == "between":
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError(f"'between' on {self.field!r} needs exactly two values")
        elif isinstance(self.value, list):
            raise ValueError(f"{self.op!r} on {self.field!r} takes a scalar, not a list")
        return self


class Period(_Model):
    grain: Grain = "month"
    start: date | None = None
    end: date | None = None
    relative: RelativePeriod | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> "Period":
        if self.relative is None and self.start is None and self.end is None:
            raise ValueError("period needs either `relative` or an explicit start/end")
        if self.start and self.end and self.start > self.end:
            raise ValueError("period start is after its end")
        return self

    @property
    def is_resolved(self) -> bool:
        """True once concrete dates are pinned - the executor requires this."""
        return self.start is not None and self.end is not None


class OrderBy(_Model):
    field: str = Field(description="A metric id or dimension id also present in the spec.")
    direction: Literal["asc", "desc"] = "desc"


class QuerySpec(_Model):
    """A question reduced to structure. Compiles to SQL with no LLM in the loop."""

    metrics: list[str] = Field(min_length=1, description="Metric ids from metrics.yaml.")
    dimensions: list[str] = Field(default_factory=list, description="Dimension ids to group by.")
    filters: list[Filter] = Field(default_factory=list)
    having: list[Filter] = Field(
        default_factory=list,
        description="Aggregate metric conditions applied after grouping, such as outstanding = 0.",
    )
    period: Period
    compare_to: Period | None = Field(
        default=None, description="Present ⇒ variance output (A, B, Δ, Δ%)."
    )
    order_by: OrderBy | None = None
    limit: int = Field(default=200, ge=1, le=5000)
    as_share: bool = Field(
        default=False,
        description="The question asks for a mix, share or composition rather than a "
        "comparison of magnitudes ('split of the book by product', 'what share is gold'). "
        "Selects part-to-whole forms; it does not change the numbers.",
    )
    """Part-to-whole is an intent, not a shape: the same rows answer "disbursement by
    product" and "our product mix", and only the question says which. Without this the
    backend can never justify a donut, because every donut candidate is also a perfectly
    good bar — and a donut chosen by shape alone would replace better bars everywhere."""

    explain: bool = Field(
        default=False,
        description="The question asks *why* the metric moved, not what it is. Requires "
        "`compare_to` and at least one dimension to attribute the change across; the change "
        "is decomposed into each member's contribution instead of being tabulated as a "
        "variance.",
    )

    @model_validator(mode="after")
    def _check_explain_is_answerable(self) -> "QuerySpec":
        # A decomposition with nothing to decompose across, or no change to decompose, is
        # not a weaker answer — it is a different question, and would silently render as a
        # one-bar waterfall. Refuse it at the contract instead.
        if not self.explain:
            return self
        if self.compare_to is None:
            raise ValueError("explain needs `compare_to` — there is no change without one")
        if not self.dimensions:
            raise ValueError("explain needs a dimension to attribute the change across")
        # `metrics[0]` is the subject. A ratio carries its denominator as a second metric so
        # the mix/rate split stays exact; anything beyond that is a multi-metric question
        # wearing an explanation's clothes.
        if len(self.metrics) > 2:
            raise ValueError("explain decomposes one metric, optionally carrying its weight")
        return self

    @model_validator(mode="after")
    def _check_no_duplicates(self) -> "QuerySpec":
        for name, ids in (("metrics", self.metrics), ("dimensions", self.dimensions)):
            if len(set(ids)) != len(ids):
                raise ValueError(f"duplicate entries in {name}")
        return self

    def cache_key(self) -> str:
        """Stable hash for the plan/result cache. Key ordering is normalised so two
        semantically identical specs collide as intended."""
        payload = json.dumps(
            self.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------------------
# Planner output
# --------------------------------------------------------------------------------------


class QuerySpecPlan(_Model):
    route: Literal["queryspec"] = "queryspec"
    spec: QuerySpec
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="", max_length=500)


class SqlPlan(_Model):
    """Catalog miss: hand off to text-to-SQL, which runs behind validator.py."""

    route: Literal["sql"] = "sql"
    intent: str
    tables: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="", max_length=500)


class ClarifyPlan(_Model):
    route: Literal["clarify"] = "clarify"
    question: str
    suggestions: list[str] = Field(default_factory=list, max_length=3)


class RefusalPlan(_Model):
    route: Literal["refuse"] = "refuse"
    reason: Literal["out_of_scope", "not_in_data", "predictive", "advice", "unsafe"]
    message: str = ""
    examples: list[str] = Field(default_factory=list, max_length=3)


PlanResult = Annotated[
    Union[QuerySpecPlan, SqlPlan, ClarifyPlan, RefusalPlan], Field(discriminator="route")
]
"""Tagged union emitted by the planner under constrained decoding."""


# --------------------------------------------------------------------------------------
# Execution result
# --------------------------------------------------------------------------------------


class Lineage(_Model):
    """Attached to every answer. The difference between a demo and a tool a CFO trusts."""

    path: Literal["queryspec", "text_to_sql"]
    sql: str
    display_sql: str = Field(
        default="",
        description="Runnable explanatory SQL with trusted bound values rendered as literals.",
    )
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Named values used by the read-only execution query.",
    )
    source_tables: list[str] = Field(default_factory=list)
    formulas: dict[str, str] = Field(default_factory=dict, description="metric id → formula text")
    row_count: int = 0
    duration_ms: int = 0
    as_of: date | None = None
    warnings: list[str] = Field(default_factory=list)
    unverified: bool = Field(
        default=False,
        description="True on the text-to-SQL path — the UI marks these answers visually.",
    )
    requires_signoff: list[str] = Field(
        default_factory=list, description="Metric ids whose definition is not yet client-ratified."
    )


class ColumnSpec(_Model):
    name: str = Field(description="Key in each row dict.")
    label: str
    unit: Unit = "text"
    format: str | None = None
    sensitivity: Sensitivity = "internal"
    masked: bool = Field(default=False, description="Values were masked for the caller's role.")


class AxisSpec(_Model):
    field: str
    label: str
    grain: Grain | None = None
    unit: Unit = "text"


class SeriesSpec(_Model):
    field: str = Field(description="Row key holding this series' value.")
    label: str
    unit: Unit = "count"
    # No `axis` field. It existed, was never set to "right" by the compiler and never read
    # by the renderer — a dual-axis affordance waiting to be discovered. Two measures of
    # different scale get two charts or a common index, never two y-scales on one plot.


class DrillStep(_Model):
    """One offered next question, with the spec that answers it already built.

    The spec is the point. A chip the user taps runs through `/nlq/execute` with no model in
    the loop, so drilling is instant, free, and cannot be misunderstood — the same property
    that makes structural follow-ups trustworthy."""

    kind: Literal["deeper", "sideways", "explain", "act"]
    id: str = Field(description="Stable within one answer, so the UI can key on it.")
    label: str = Field(description="Chip text, e.g. 'By agent'.")
    question: str = Field(description="Standalone phrasing, for the audit log and history.")
    dimension: str | None = Field(
        default=None, description="The dimension this step moves to, where it moves to one."
    )
    spec: QuerySpec


class ChartSpec(_Model):
    """The single response payload. `rows` is always populated — even for `kpi` and
    `line` — so the table view, CSV export and representation toggle cost no round-trip."""

    chart_type: ChartType
    title: str
    subtitle: str | None = None
    x: AxisSpec | None = None
    series_by: AxisSpec | None = Field(
        default=None,
        description="Dimension that splits `rows` into one series per value — the second "
        "axis of a heatmap, the facet of a small-multiples grid. Rows arrive long-format; "
        "this names the column to pivot on so the renderer never has to guess.",
    )
    series: list[SeriesSpec] = Field(default_factory=list)
    columns: list[ColumnSpec] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = Field(default="", description="Deterministic narration, templated from rows.")
    drilldown: QuerySpec | None = None
    next_steps: list[DrillStep] = Field(
        default_factory=list,
        description="Where this answer can go next, derived from the catalog's drill graph. "
        "An answer that carries its own follow-ups is what turns a chart into a chain.",
    )
    lineage: Lineage


# --------------------------------------------------------------------------------------
# Conversation + API envelope
# --------------------------------------------------------------------------------------


class Turn(_Model):
    question: str
    resolved_question: str
    route: Literal["queryspec", "sql", "clarify", "refuse"]
    chart_type: ChartType | None = None
    row_count: int = 0
    ts: datetime


class ConversationState(_Model):
    conversation_id: str
    turns: list[Turn] = Field(default_factory=list, description="Last 5 retained.")
    active_spec: QuerySpec | None = Field(default=None, description="Anchor for follow-ups.")
    entities: dict[str, str] = Field(
        default_factory=dict, description="Sticky filters, e.g. {'branch': '3'} — shown in the UI."
    )
    updated_at: datetime | None = None


class AskResponse(_Model):
    conversation_id: str
    turn_id: str
    status: Literal["answered", "clarify", "refused"]
    chart: ChartSpec | None = None
    clarification: ClarifyPlan | None = None
    refusal: RefusalPlan | None = None
    plan_summary: str = ""
