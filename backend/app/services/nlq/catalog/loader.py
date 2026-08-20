"""Load and validate the YAML catalog into typed objects.

Validation happens at import, not at query time: a catalog that references a metric's
base table without a join path, or a dimension with no enum block, is a bug that must
surface on startup rather than in front of a user mid-question.

What this module deliberately does NOT do is check that the columns exist in Postgres —
that needs a database and belongs in the introspection test
(backend/tests/nlq/test_catalog_introspection.py), which fails the moment the warehouse
drifts from the catalog.
"""

from __future__ import annotations

import functools
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

DEFS_DIR = Path(__file__).resolve().parent / "defs"
ACTIVE_DEFS_DIR = DEFS_DIR / "gold"

_WORD_RE = re.compile(r"[a-z0-9]+")
_INTEGRAL_DECIMAL_CODE_RE = re.compile(r"^-?\d+\.0+$")


def canonical_enum_code(code: Any) -> str:
    """Normalise JSON-safe numeric codes without damaging opaque string identifiers.

    PostgreSQL ``numeric`` values are converted to floats by the result executor so product
    code 16 reaches the chart layer as ``16.0``.  Curated enum keys are strings such as
    ``"16"``.  Exact text is preserved unless it is unambiguously an integral decimal;
    alphanumeric codes (SMA0), leading-zero strings and non-integral rates are untouched.
    """
    key = str(code).strip()
    if _INTEGRAL_DECIMAL_CODE_RE.fullmatch(key):
        integer = key.split(".", 1)[0]
        # Numeric database codes do not use significant leading zeroes.  Keep a single zero
        # and preserve a possible minus sign.
        sign = "-" if integer.startswith("-") else ""
        digits = integer.removeprefix("-").lstrip("0") or "0"
        return sign + digits
    return key


class CatalogError(RuntimeError):
    """A malformed or internally inconsistent catalog. Always fatal."""


# --------------------------------------------------------------------------------------
# Typed entries
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Table:
    id: str
    table: str
    label: str
    grain: str
    description: str = ""
    synonyms: tuple[str, ...] = ()
    key: tuple[str, ...] = ()
    row_count: int | None = None
    is_hub: bool = False
    point_in_time: bool = False
    as_of_column: str | None = None
    year_column: str | None = None
    date_columns: dict[str, str] = field(default_factory=dict)
    contains_pii: bool = False
    notes: str = ""
    coverage_warning: str = ""
    restrictions: str = ""

    @property
    def schema(self) -> str:
        return self.table.split(".", 1)[0]


@dataclass(frozen=True, slots=True)
class Column:
    id: str
    table: str
    column: str
    label: str
    unit: str = "text"
    synonyms: tuple[str, ...] = ()
    description: str = ""
    sensitivity: Literal["public", "internal", "pii"] = "internal"
    agg: tuple[str, ...] = ()
    decode: str | None = None

    @property
    def is_pii(self) -> bool:
        return self.sensitivity == "pii"


@dataclass(frozen=True, slots=True)
class Dimension:
    id: str
    label: str
    type: Literal["categorical", "time"]
    table: str | None = None
    column: str | None = None
    grain: str | None = None
    decode: str | None = None
    expression: str | None = None
    sort_expression: str | None = None
    synonyms: tuple[str, ...] = ()
    description: str = ""
    cardinality: int | None = None
    point_in_time: bool = False

    @property
    def is_time(self) -> bool:
        return self.type == "time"

    def sql(self, alias: str) -> str:
        """The grouping expression for this dimension, qualified by table alias."""
        if self.is_time:
            raise CatalogError(f"time dimension {self.id!r} is resolved by the compiler, not here")
        qualified = f'{alias}."{self.column}"'
        if self.expression:
            return " ".join(self.expression.replace("{col}", qualified).split())
        return qualified

    def sort_sql(self, alias: str) -> str | None:
        if not self.sort_expression:
            return None
        return " ".join(self.sort_expression.replace("{col}", f'{alias}."{self.column}"').split())


@dataclass(frozen=True, slots=True)
class Metric:
    id: str
    label: str
    unit: str
    grain: Literal["flow", "point_in_time", "ratio"]
    base_table: str
    formula: str
    expression: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    scale: float = 1.0
    date_column: str | None = None
    as_of_column: str | None = None
    as_of_key: tuple[str, ...] = ()
    as_of_function: str | None = None
    year_column: str | None = None
    synonyms: tuple[str, ...] = ()
    description: str = ""
    caveat: str = ""
    requires_signoff: bool = False
    signoff_note: str = ""
    point_in_time: bool = False
    no_time_travel: bool = False
    restrictions: str = ""
    verified: str = ""
    weight_metric: str | None = None
    """For a ratio, the metric that *is* its denominator.

    Driver decomposition splits a ratio's change into a mix effect and a rate effect, and
    that split is only exact if each member's weight is known. Naming the denominator as a
    metric — rather than re-deriving it from the SQL expression — keeps the weight governed
    by the same catalog the numbers come from."""

    @property
    def is_ratio(self) -> bool:
        return self.numerator is not None

    @property
    def needs_as_of(self) -> bool:
        """True when the metric reads an event log that must be collapsed to one row per
        account before aggregation. This is the guard against the classification-event trap."""
        return bool(self.as_of_function or (self.as_of_column and self.as_of_key))

    def sql(self, alias: str) -> str:
        """Aggregate expression for this metric, qualified by table alias."""
        if self.is_ratio:
            num = self._sub(self.numerator, alias)
            den = self._sub(self.denominator, alias)
            scale = f"{self.scale} * " if self.scale != 1.0 else ""
            # Two different nulls, two different meanings:
            #   numerator NULL   -> the FILTER matched nothing. That is a real zero: no
            #                       account is over 90 DPD. COALESCE it, or PAR 90 reports
            #                       "no data" when the honest answer is 0.000%.
            #   denominator zero -> there is nothing to take a ratio of. NULLIF keeps that
            #                       as "no data" rather than a division-by-zero mid-report.
            return f"({scale}COALESCE({num}, 0) / NULLIF({den}, 0))"
        return self._sub(self.expression, alias)

    @staticmethod
    def _sub(expr: str | None, alias: str) -> str:
        if not expr:
            raise CatalogError("metric has neither an expression nor a numerator")
        return " ".join(expr.replace("{t}", alias).split())


@dataclass(frozen=True, slots=True)
class Join:
    id: str
    left: str
    right: str
    on: tuple[tuple[str, str], ...]
    cardinality: Literal["many_to_one", "one_to_many", "one_to_one", "many_to_many"]
    join_type: Literal["inner", "left"] = "inner"
    contains_pii: bool = False
    description: str = ""
    verified: str = ""

    @property
    def fans_out(self) -> bool:
        """True when following this edge can multiply rows on the left — which would
        double-count any SUM taken from the left table (§2.5 rule 4)."""
        return self.cardinality in ("one_to_many", "many_to_many")


@dataclass(frozen=True, slots=True)
class AnalysisStepDef:
    """One query in a preset analysis, still in catalog terms rather than as a QuerySpec.

    Kept as loose data here so the catalog stays importable without the contracts module;
    `analysis.build` turns it into a real `QuerySpec` and the validators there apply."""

    id: str
    label: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    order_by: dict[str, str] | None = None
    limit: int | None = None
    as_share: bool = False
    watch_above: float | None = None
    watch_below: float | None = None
    alert_above: float | None = None
    alert_below: float | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class AnalysisDef:
    """A question that takes more than one query, defined once and reviewed once."""

    id: str
    title: str
    compose: str
    steps: tuple[AnalysisStepDef, ...]
    description: str = ""
    synonyms: tuple[str, ...] = ()
    default_period: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DrillPath:
    """One axis a question can be drilled along, coarsest rung first."""

    id: str
    label: str
    levels: tuple[str, ...]
    pending: tuple[str, ...] = ()
    """Rungs the business asks for that no data source can currently fill. Declared rather
    than omitted so the gap is visible, and so filling it is a YAML edit."""
    primary: bool = False
    """Whether this path's head is worth offering as the first split of any total."""

    @property
    def active_levels(self) -> tuple[str, ...]:
        return self.levels

    def index_of(self, level: str) -> int | None:
        try:
            return self.levels.index(level)
        except ValueError:
            return None

    def next_after(self, level: str) -> str | None:
        position = self.index_of(level)
        if position is None:
            return None
        return self.levels[position + 1] if position + 1 < len(self.levels) else None


@dataclass(frozen=True, slots=True)
class DrillGraph:
    """Where any answer can go next. Configuration, not a hardcoded ladder."""

    paths: tuple[DrillPath, ...]
    entity: str
    entity_limit: int = 50
    offers: tuple[str, ...] = ()

    def path_for(self, level: str) -> DrillPath | None:
        return next((p for p in self.paths if p.index_of(level) is not None), None)

    def heads(self, *, primary_only: bool = False) -> tuple[str, ...]:
        return tuple(
            p.levels[0] for p in self.paths
            if p.levels and (p.primary or not primary_only)
        )


@dataclass(frozen=True, slots=True)
class EnumValue:
    code: str
    label: str
    synonyms: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True, slots=True)
class EnumBlock:
    dimension: str
    column: str
    values: dict[str, EnumValue]
    source: str = ""
    note: str = ""
    fallback_label: str = "{code}"
    lookup: dict[str, Any] = field(default_factory=dict)

    def label_for(self, code: Any) -> str:
        key = canonical_enum_code(code)
        entry = self.values.get(key)
        if entry:
            return entry.label
        return self.fallback_label.replace("{code}", key)

    def code_for(self, text: str) -> str | None:
        """Resolve a user's word to a code. Exact label or synonym match only — a fuzzy
        match here would silently answer about the wrong product. Ambiguous governed names
        also return ``None``: two schemes with the same label must never collapse to the
        first code merely because it appears first in YAML."""
        needle = text.strip().lower()
        matches = [
            code
            for code, value in self.values.items()
            if value.label.lower() == needle or needle in (s.lower() for s in value.synonyms)
        ]
        return matches[0] if len(matches) == 1 else None


# --------------------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Catalog:
    tables: dict[str, Table]
    columns: dict[str, Column]
    dimensions: dict[str, Dimension]
    metrics: dict[str, Metric]
    joins: tuple[Join, ...]
    enums: dict[str, EnumBlock]
    drill: DrillGraph
    analyses: dict[str, AnalysisDef]
    version: str

    # -- lookup helpers ------------------------------------------------------------------

    def table_by_name(self, qualified: str) -> Table | None:
        return next((t for t in self.tables.values() if t.table == qualified), None)

    def columns_for(self, qualified_table: str) -> list[Column]:
        return [c for c in self.columns.values() if c.table == qualified_table]

    def allowed_tables(self) -> set[str]:
        """The full allowlist the SQL validator enforces on the text-to-SQL path."""
        return {t.table for t in self.tables.values()}

    def pii_columns(self) -> set[tuple[str, str]]:
        return {(c.table, c.column) for c in self.columns.values() if c.is_pii}

    def join_between(self, left: str, right: str) -> Join | None:
        """The single declared edge between two tables, in either direction.

        Returns None when there is no path — the compiler turns that into a refusal rather
        than inventing a join condition.
        """
        matches = [
            j for j in self.joins
            if {j.left, j.right} == {left, right}
        ]
        if len(matches) > 1:
            raise CatalogError(f"ambiguous join path between {left} and {right}")
        return matches[0] if matches else None

    def enum_for_dimension(self, dimension_id: str) -> EnumBlock | None:
        return self.enums.get(dimension_id)

    def search_metrics(self, text: str) -> list[Metric]:
        """Lexical synonym hit. Short acronyms like PAR and DPD embed poorly but match
        here with certainty, which is why retrieval scores this alongside vectors."""
        needle = text.lower()
        tokens = [t for t in _WORD_RE.findall(needle) if len(t) >= 4]
        hits = []
        for metric in self.metrics.values():
            haystack = [metric.id, metric.label, *metric.synonyms]
            if any(term.lower() in needle for term in haystack):
                hits.append(metric)
                continue
            # Crude stemming, deliberately one-directional: "disburse" in the question
            # should reach the "disbursement" synonym. Requiring a 4-character shared
            # prefix keeps "loan" from matching everything.
            if any(
                term.lower().startswith(token) or token.startswith(term.lower())
                for term in haystack
                for token in tokens
                if len(term) >= 4
            ):
                hits.append(metric)
        return hits


def _read(name: str) -> list[dict[str, Any]]:
    # Gold is the only active semantic layer. Missing Gold metadata is fatal; silently
    # falling back to the legacy Silver catalog would widen the LLM's database surface.
    path = ACTIVE_DEFS_DIR / name
    if not path.exists():
        raise CatalogError(f"catalog file missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise CatalogError(f"{name} must contain a YAML list, got {type(data).__name__}")
    return data


def _read_mapping(name: str) -> dict[str, Any]:
    path = ACTIVE_DEFS_DIR / name
    if not path.exists():
        raise CatalogError(f"catalog file missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CatalogError(f"{name} must contain a YAML mapping, got {type(data).__name__}")
    return data


def _tuple(value: Any) -> tuple:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _require(entry: dict[str, Any], *keys: str, where: str) -> None:
    missing = [k for k in keys if entry.get(k) in (None, "")]
    if missing:
        raise CatalogError(f"{where}: entry {entry.get('id', '?')!r} is missing {missing}")


def _load_tables() -> dict[str, Table]:
    out: dict[str, Table] = {}
    for raw in _read("tables.yaml"):
        _require(raw, "id", "table", "label", "grain", where="tables.yaml")
        out[raw["id"]] = Table(
            id=raw["id"],
            table=raw["table"],
            label=raw["label"],
            grain=raw["grain"],
            description=raw.get("description", ""),
            synonyms=_tuple(raw.get("synonyms")),
            key=_tuple(raw.get("key")),
            row_count=raw.get("row_count"),
            is_hub=bool(raw.get("is_hub")),
            point_in_time=bool(raw.get("point_in_time")),
            as_of_column=raw.get("as_of_column"),
            year_column=raw.get("year_column"),
            date_columns=raw.get("date_columns") or {},
            contains_pii=bool(raw.get("contains_pii")),
            notes=raw.get("notes", ""),
            coverage_warning=raw.get("coverage_warning", ""),
            restrictions=raw.get("restrictions", ""),
        )
    if not any(t.is_hub for t in out.values()):
        raise CatalogError("no hub table declared — the join graph would have no centre")
    return out


def _load_columns() -> dict[str, Column]:
    out: dict[str, Column] = {}
    for raw in _read("columns.yaml"):
        _require(raw, "id", "table", "column", "label", where="columns.yaml")
        out[raw["id"]] = Column(
            id=raw["id"],
            table=raw["table"],
            column=raw["column"],
            label=raw["label"],
            unit=raw.get("unit", "text"),
            synonyms=_tuple(raw.get("synonyms")),
            description=raw.get("description", ""),
            sensitivity=raw.get("sensitivity", "internal"),
            agg=_tuple(raw.get("agg")),
            decode=raw.get("decode"),
        )
    return out


def _load_dimensions() -> dict[str, Dimension]:
    out: dict[str, Dimension] = {}
    for raw in _read("dimensions.yaml"):
        _require(raw, "id", "label", "type", where="dimensions.yaml")
        kind = raw["type"]
        if kind not in ("categorical", "time"):
            raise CatalogError(f"dimension {raw['id']!r} has unknown type {kind!r}")
        if kind == "categorical":
            _require(raw, "table", "column", where="dimensions.yaml")
        else:
            _require(raw, "grain", where="dimensions.yaml")
        out[raw["id"]] = Dimension(
            id=raw["id"],
            label=raw["label"],
            type=kind,
            table=raw.get("table"),
            column=raw.get("column"),
            grain=raw.get("grain"),
            decode=raw.get("decode"),
            expression=raw.get("expression"),
            sort_expression=raw.get("sort_expression"),
            synonyms=_tuple(raw.get("synonyms")),
            description=raw.get("description", ""),
            cardinality=raw.get("cardinality"),
            point_in_time=bool(raw.get("point_in_time")),
        )
    return out


def _load_metrics() -> dict[str, Metric]:
    out: dict[str, Metric] = {}
    for raw in _read("metrics.yaml"):
        _require(raw, "id", "label", "unit", "grain", "base_table", "formula",
                 where="metrics.yaml")
        has_expr = bool(raw.get("expression"))
        has_ratio = bool(raw.get("numerator")) and bool(raw.get("denominator"))
        if has_expr == has_ratio:
            raise CatalogError(
                f"metric {raw['id']!r} must declare either `expression` or both "
                "`numerator` and `denominator`, not neither and not both"
            )
        if raw["grain"] not in ("flow", "point_in_time", "ratio"):
            raise CatalogError(f"metric {raw['id']!r} has unknown grain {raw['grain']!r}")
        out[raw["id"]] = Metric(
            id=raw["id"],
            label=raw["label"],
            unit=raw["unit"],
            grain=raw["grain"],
            base_table=raw["base_table"],
            formula=raw["formula"],
            expression=raw.get("expression"),
            numerator=raw.get("numerator"),
            denominator=raw.get("denominator"),
            scale=float(raw.get("scale", 1.0)),
            date_column=raw.get("date_column"),
            as_of_column=raw.get("as_of_column"),
            as_of_key=_tuple(raw.get("as_of_key")),
            as_of_function=raw.get("as_of_function"),
            year_column=raw.get("year_column"),
            synonyms=_tuple(raw.get("synonyms")),
            description=raw.get("description", ""),
            caveat=raw.get("caveat", ""),
            requires_signoff=bool(raw.get("requires_signoff")),
            signoff_note=raw.get("signoff_note", ""),
            point_in_time=bool(raw.get("point_in_time")),
            no_time_travel=bool(raw.get("no_time_travel")),
            restrictions=raw.get("restrictions", ""),
            verified=str(raw.get("verified", "")),
            weight_metric=raw.get("weight_metric"),
        )
    return out


def _load_analyses() -> dict[str, AnalysisDef]:
    out: dict[str, AnalysisDef] = {}
    for raw in _read("analyses.yaml"):
        _require(raw, "id", "title", "compose", "steps", where="analyses.yaml")
        steps = []
        for entry in raw["steps"]:
            _require(entry, "id", "label", "metrics", where=f"analyses.yaml/{raw['id']}")
            steps.append(
                AnalysisStepDef(
                    id=entry["id"],
                    label=entry["label"],
                    metrics=_tuple(entry["metrics"]),
                    dimensions=_tuple(entry.get("dimensions")),
                    order_by=entry.get("order_by"),
                    limit=entry.get("limit"),
                    as_share=bool(entry.get("as_share")),
                    watch_above=entry.get("watch_above"),
                    watch_below=entry.get("watch_below"),
                    alert_above=entry.get("alert_above"),
                    alert_below=entry.get("alert_below"),
                    note=entry.get("note", ""),
                )
            )
        out[raw["id"]] = AnalysisDef(
            id=raw["id"],
            title=raw["title"],
            compose=raw["compose"],
            steps=tuple(steps),
            description=raw.get("description", ""),
            synonyms=_tuple(raw.get("synonyms")),
            default_period=raw.get("default_period") or {},
        )
    return out


def _load_drill() -> DrillGraph:
    raw = _read_mapping("drill.yaml")
    paths = []
    for entry in raw.get("paths") or []:
        _require(entry, "id", "label", "levels", where="drill.yaml")
        paths.append(
            DrillPath(
                id=entry["id"],
                label=entry["label"],
                levels=_tuple(entry["levels"]),
                pending=_tuple(entry.get("pending")),
                primary=bool(entry.get("primary")),
            )
        )
    terminal = raw.get("terminal") or {}
    if not terminal.get("entity"):
        raise CatalogError("drill.yaml must declare terminal.entity — a chain needs an end")
    return DrillGraph(
        paths=tuple(paths),
        entity=terminal["entity"],
        entity_limit=int(terminal.get("limit", 50)),
        offers=_tuple(raw.get("offers")),
    )


def _load_joins() -> tuple[Join, ...]:
    joins = []
    for raw in _read("joins.yaml"):
        # `on_columns`, not `on`: YAML 1.1 parses a bare `on:` key as the boolean True,
        # so the obvious spelling silently loses the join condition.
        _require(raw, "id", "left", "right", "on_columns", "cardinality", where="joins.yaml")
        pairs = tuple((a, b) for a, b in raw["on_columns"])
        if not pairs:
            raise CatalogError(f"join {raw['id']!r} has no ON columns — that is a cross join")
        joins.append(
            Join(
                id=raw["id"],
                left=raw["left"],
                right=raw["right"],
                on=pairs,
                cardinality=raw["cardinality"],
                join_type=raw.get("join_type", "inner"),
                contains_pii=bool(raw.get("contains_pii")),
                description=raw.get("description", ""),
                verified=str(raw.get("verified", "")),
            )
        )
    return tuple(joins)


def _load_enums() -> dict[str, EnumBlock]:
    out: dict[str, EnumBlock] = {}
    for raw in _read("enums.yaml"):
        _require(raw, "dimension", "column", where="enums.yaml")
        values: dict[str, EnumValue] = {}
        for code, spec in (raw.get("values") or {}).items():
            if isinstance(spec, str):
                spec = {"label": spec}
            values[str(code)] = EnumValue(
                code=str(code),
                label=spec.get("label", str(code)),
                synonyms=_tuple(spec.get("synonyms")),
                note=spec.get("note", ""),
            )
        out[raw["dimension"]] = EnumBlock(
            dimension=raw["dimension"],
            column=raw["column"],
            values=values,
            source=raw.get("source", ""),
            note=raw.get("note", ""),
            fallback_label=raw.get("fallback_label", "{code}"),
            lookup=raw.get("lookup") or {},
        )
    return out


def _drill_problems(catalog: Catalog) -> list[str]:
    """The drill graph is navigation, so a broken rung is a dead end in front of a user."""
    problems: list[str] = []
    graph = catalog.drill
    seen: dict[str, str] = {}

    for path in graph.paths:
        if not path.levels:
            problems.append(f"drill path {path.id!r} has no active levels")
        for level in path.levels:
            if level not in catalog.dimensions:
                problems.append(f"drill path {path.id!r} names unknown level {level!r}")
            elif catalog.dimensions[level].is_time:
                # Time is orthogonal to drilling: every level keeps whatever time grain the
                # question already had, so a time dimension as a rung would fight it.
                problems.append(f"drill path {path.id!r} uses time dimension {level!r} as a rung")
            if level in seen:
                problems.append(
                    f"level {level!r} appears in both {seen[level]!r} and {path.id!r} — "
                    "'one level deeper' would be ambiguous"
                )
            seen[level] = path.id
        for level in path.pending:
            if level in catalog.dimensions:
                problems.append(
                    f"drill path {path.id!r} lists {level!r} as pending, but it is now a "
                    "real dimension — promote it into `levels`"
                )

    if graph.entity not in catalog.dimensions:
        problems.append(f"drill terminal entity {graph.entity!r} is not a dimension")

    unknown = set(graph.offers) - {"explain", "act"}
    if unknown:
        problems.append(f"drill.yaml offers unknown step kinds {sorted(unknown)}")

    return problems


_COMPOSERS = {"briefing", "quadrant", "concentration"}

# A composer that receives the wrong shape does not fail — it produces a confident,
# meaningless answer. Pin the shape each one requires at load time instead.
# (step count, metrics per step, dimensions per step, description)
_COMPOSER_SHAPES = {
    "quadrant": (2, 1, 1, "two steps of one metric over the same one dimension"),
    "concentration": (1, 1, 1, "exactly one step with one metric and one dimension"),
}


def _analysis_problems(catalog: Catalog) -> list[str]:
    problems: list[str] = []
    for analysis in catalog.analyses.values():
        where = f"analysis {analysis.id!r}"
        if analysis.compose not in _COMPOSERS:
            problems.append(f"{where} uses unknown composer {analysis.compose!r}")

        for step in analysis.steps:
            for metric in step.metrics:
                if metric not in catalog.metrics:
                    problems.append(f"{where} step {step.id!r} names unknown metric {metric!r}")
            for dim in step.dimensions:
                if dim not in catalog.dimensions:
                    problems.append(f"{where} step {step.id!r} names unknown dimension {dim!r}")
            if step.order_by:
                field_name = step.order_by.get("field")
                if field_name not in {*step.metrics, *step.dimensions}:
                    problems.append(
                        f"{where} step {step.id!r} orders by {field_name!r}, which the step "
                        "does not select"
                    )

        if len(analysis.steps) != len({s.id for s in analysis.steps}):
            problems.append(f"{where} has duplicate step ids")

        shape = _COMPOSER_SHAPES.get(analysis.compose)
        if shape:
            n_steps, n_metrics, n_dims, described = shape
            ok = len(analysis.steps) == n_steps and all(
                len(s.metrics) == n_metrics and len(s.dimensions) == n_dims
                for s in analysis.steps
            )
            if ok and n_steps > 1:
                # The steps are merged on their shared dimension, so they must share one.
                ok = len({s.dimensions for s in analysis.steps}) == 1
            if not ok:
                problems.append(
                    f"{where} composes with {analysis.compose!r}, which needs {described}"
                )

    return problems


def _cross_validate(catalog: Catalog) -> None:
    """Every reference must resolve. These are the errors that would otherwise surface as
    a broken query in front of a user."""
    known_tables = catalog.allowed_tables()
    problems: list[str] = []

    for column in catalog.columns.values():
        if column.table not in known_tables:
            problems.append(f"column {column.id!r} references unknown table {column.table!r}")
        if column.decode and column.decode not in catalog.enums:
            problems.append(f"column {column.id!r} decodes with unknown enum {column.decode!r}")

    for dim in catalog.dimensions.values():
        if dim.is_time:
            continue
        if dim.table not in known_tables:
            problems.append(f"dimension {dim.id!r} references unknown table {dim.table!r}")
        if dim.decode and dim.decode not in catalog.enums:
            problems.append(f"dimension {dim.id!r} decodes with unknown enum {dim.decode!r}")
        if dim.sort_expression and not dim.expression:
            problems.append(f"dimension {dim.id!r} has a sort expression but no expression")

    for metric in catalog.metrics.values():
        if metric.base_table not in known_tables:
            problems.append(f"metric {metric.id!r} has unknown base table {metric.base_table!r}")
        if metric.grain == "point_in_time" and not (
            metric.as_of_column or metric.as_of_function or metric.no_time_travel
            or metric.year_column
        ):
            problems.append(
                f"metric {metric.id!r} is point_in_time but declares no as_of_column — the "
                "compiler could not pin it to a date and would silently average it"
            )
        if metric.as_of_column and not metric.as_of_key and not metric.as_of_function:
            problems.append(
                f"metric {metric.id!r} has an as_of_column but no as_of_key, so the "
                "compiler cannot collapse the event log to one row per entity"
            )

    for metric in catalog.metrics.values():
        weight = metric.weight_metric
        if not weight:
            continue
        if not metric.is_ratio:
            problems.append(
                f"metric {metric.id!r} declares a weight_metric but is not a ratio — there "
                "is nothing for a weight to weight"
            )
        elif weight not in catalog.metrics:
            problems.append(f"metric {metric.id!r} weights by unknown metric {weight!r}")
        elif catalog.metrics[weight].base_table != metric.base_table:
            # A weight drawn from a different table is a different population, so the mix
            # and rate effects would stop summing to the change they claim to explain.
            problems.append(
                f"metric {metric.id!r} weights by {weight!r}, which sits on a different "
                "base table"
            )

    problems.extend(_drill_problems(catalog))
    problems.extend(_analysis_problems(catalog))

    for join in catalog.joins:
        for side in (join.left, join.right):
            if side not in known_tables:
                problems.append(f"join {join.id!r} references unknown table {side!r}")

    # Every non-hub fact table a metric reads must be able to reach the hub, or its metrics
    # can never be grouped by product/branch/scheme.
    hub = next(t.table for t in catalog.tables.values() if t.is_hub)
    for metric in catalog.metrics.values():
        if metric.base_table == hub:
            continue
        table_entry = catalog.table_by_name(metric.base_table)
        if table_entry and table_entry.restrictions:
            continue  # deliberately isolated (GL), documented as such
        if catalog.join_between(metric.base_table, hub) is None:
            problems.append(
                f"metric {metric.id!r} sits on {metric.base_table!r}, which has no declared "
                f"join to the hub {hub!r} and no documented restriction"
            )

    if problems:
        raise CatalogError("catalog validation failed:\n  - " + "\n  - ".join(problems))


def _version(paths: Iterable[Path]) -> str:
    """Content hash of the definitions. Bumping it invalidates the embedding index and the
    plan cache, so a catalog edit cannot leave stale vectors behind."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@functools.lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    version_paths = [
        ACTIVE_DEFS_DIR / name
        for name in (
            "tables.yaml", "columns.yaml", "dimensions.yaml", "metrics.yaml",
            "joins.yaml", "enums.yaml", "drill.yaml", "analyses.yaml",
        )
    ]
    catalog = Catalog(
        tables=_load_tables(),
        columns=_load_columns(),
        dimensions=_load_dimensions(),
        metrics=_load_metrics(),
        joins=_load_joins(),
        enums=_load_enums(),
        drill=_load_drill(),
        analyses=_load_analyses(),
        version=_version(version_paths),
    )
    _cross_validate(catalog)
    return catalog
