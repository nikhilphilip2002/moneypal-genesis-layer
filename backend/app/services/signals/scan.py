"""The scan: run every configured scope, hand the series to the detectors, store what fired.

Runs on a schedule rather than on a question. That is the whole point — "what are the
emerging issues?" has no answer at request time, because there is no baseline to compare
against and nothing has been ranked. Running it nightly turns the question into retrieval
over pre-computed evidence, and every signal carries the `QuerySpec` that produced it, so a
finding is one click from the chart behind it.

Every number still comes from the ordinary compiler and executor. The scan invents no SQL of
its own beyond the freshness checks, which read one `MAX(date)` per table.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from datetime import date, datetime, timezone
from typing import Any

from app.services.nlq import periods
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.loader import DataHealthCheck, SignalScope, canonical_enum_code
from app.services.nlq.compiler import CompiledQuery, CompileError, compile_spec
from app.services.nlq.contracts import Period, QuerySpec, ScanReport, Signal
from app.services.nlq.executor import ExecutionError, execute
from app.services.nlq.narrator import format_value, humanize_label
from app.services.signals import detectors

logger = logging.getLogger(__name__)

MAX_WORKERS = 3
"""Below the read-only pool, and lower than the analysis budget: the scan runs unattended
and must never be the reason a director's question waits for a connection."""

_SCOPE_SLOTS = threading.Semaphore(MAX_WORKERS)


class ScanError(RuntimeError):
    """A scan that could not run at all, as distinct from a scope that found nothing."""


def run(
    *,
    catalog: Catalog | None = None,
    today: date | None = None,
    scopes: list[str] | None = None,
) -> ScanReport:
    """Run the scan and return everything it found. Does not store — see `store.record`."""
    cat = catalog or get_catalog()
    started = time.perf_counter()
    now = datetime.now(timezone.utc)

    wanted = [
        scope for scope_id, scope in cat.signals.scopes.items()
        if scopes is None or scope_id in scopes
    ]

    signals: list[Signal] = []
    warnings: list[str] = []
    abstained: list[str] = []
    failed = 0

    def one(scope: SignalScope) -> tuple[list[Signal], str, str]:
        try:
            with _SCOPE_SLOTS:
                found = _scan_scope(scope, cat, today)
            # A scope that ran and found nothing and a scope that could not judge are
            # different results, and a dashboard that renders them the same way tells the
            # reader the book is clean when the truth is that history is too short.
            return found, "", "" if found else scope.id
        except (CompileError, ExecutionError) as exc:
            logger.warning("signal scope %s failed: %s", scope.id, exc)
            return [], f"{scope.label} could not be scanned.", ""

    workers = min(MAX_WORKERS, max(len(wanted), 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for found, warning, quiet in pool.map(one, wanted):
            signals.extend(found)
            if warning:
                warnings.append(warning)
                failed += 1
            elif quiet:
                abstained.append(quiet)

    if scopes is None:
        health, health_warnings = _scan_data_health(cat)
        signals.extend(health)
        warnings.extend(health_warnings)

    signals.sort(key=_notability)
    for signal in signals:
        signal.detected_at = now
        signal.id = signal.fingerprint

    return ScanReport(
        started_at=now,
        duration_ms=int((time.perf_counter() - started) * 1000),
        scopes_run=len(wanted),
        scopes_failed=failed,
        signals=signals,
        warnings=warnings,
        abstained=abstained,
    )


# --------------------------------------------------------------------------------------
# One scope
# --------------------------------------------------------------------------------------


def _scan_scope(scope: SignalScope, cat: Catalog, today: date | None) -> list[Signal]:
    metric = cat.metrics.get(scope.metric)
    if metric is None:  # pragma: no cover - the catalog validator rejects these
        return []

    spec = _series_spec(scope, cat)
    compiled = compile_spec(spec, cat, today)
    rows = execute(compiled).rows
    if not rows:
        return []

    if scope.dimension:
        return _scan_by_member(scope, metric, spec, rows, cat)
    return _scan_total(scope, metric, spec, rows, cat)


def _series_spec(scope: SignalScope, cat: Catalog) -> QuerySpec:
    """One monthly series per scope. A concentration scope needs no time axis — the question
    is whether the book *is* concentrated, which is asked of the book as it stands."""
    config = cat.signals
    structural = "concentration" in scope.detectors

    dimensions = []
    if not structural:
        dimensions.append(config.grain)
    if scope.dimension:
        dimensions.append(scope.dimension)

    return QuerySpec(
        metrics=[scope.metric],
        dimensions=dimensions,
        period=Period(
            grain=config.grain,  # type: ignore[arg-type]
            relative="today" if structural else _window(config.periods, config.grain),
        ),
        limit=scope.max_members or config.max_members,
    )


def _window(count: int, grain: str) -> str:
    """The closed relative-period token covering roughly `count` periods of `grain`."""
    if grain == "month" and count > 3:
        return "last_12_months"
    if grain == "day":
        return "last_90_days"
    return "last_12_months"


def _scan_total(
    scope: SignalScope, metric, spec: QuerySpec, rows: list[dict[str, Any]], cat: Catalog
) -> list[Signal]:
    grain = cat.signals.grain
    ordered = sorted(rows, key=lambda r: str(r.get(grain, "")))
    series = [_number(r.get(metric.id)) for r in ordered]
    latest = series[-1] if series else None

    found = []
    for detection in _detect(scope, series, latest):
        found.append(_signal(scope, metric, detection, spec, cat, member="", value=latest))
    return found


def _scan_by_member(
    scope: SignalScope, metric, spec: QuerySpec, rows: list[dict[str, Any]], cat: Catalog
) -> list[Signal]:
    grain = cat.signals.grain
    structural = "concentration" in scope.detectors
    dimension = scope.dimension or ""

    if structural:
        values = [_number(r.get(metric.id)) for r in rows]
        detection = detectors.concentration(
            values,
            watch_hhi=scope.watch_hhi or 1.0,
            alert_hhi=scope.alert_hhi or 1.0,
        )
        if detection is None:
            return []
        return [_signal(scope, metric, detection, spec, cat, member="", value=detection.magnitude)]

    # Rows arrive as (period, member, value). Regroup into one series per member.
    by_member: dict[str, dict[str, float | None]] = {}
    labels: dict[str, str] = {}
    for row in rows:
        raw = row.get(f"{dimension}__raw", row.get(dimension))
        if raw is None:
            continue
        key = canonical_enum_code(raw)
        labels.setdefault(key, str(row.get(dimension, key)))
        by_member.setdefault(key, {})[str(row.get(grain, ""))] = _number(row.get(metric.id))

    stamps = sorted({s for series in by_member.values() for s in series})
    if not stamps:
        return []

    found: list[Signal] = []
    for key, series in by_member.items():
        values = [series.get(stamp) for stamp in stamps]
        latest = values[-1] if values else None
        member_spec = _member_spec(spec, dimension, key, cat)
        for detection in _detect(scope, values, latest):
            found.append(
                _signal(scope, metric, detection, member_spec, cat,
                        member=labels[key], value=latest)
            )

    if "rank_movement" in scope.detectors and len(stamps) >= 2:
        current = {k: s.get(stamps[-1]) for k, s in by_member.items()}
        prior = {k: s.get(stamps[-2]) for k, s in by_member.items()}
        for key, detection in detectors.rank_movement(current, prior):
            found.append(
                _signal(scope, metric, detection, _member_spec(spec, dimension, key, cat), cat,
                        member=labels.get(key, key), value=current.get(key))
            )
    return found


def _detect(
    scope: SignalScope, series: list[float | None], latest: float | None
) -> list[detectors.Detection]:
    """Every detector the scope asked for, minus the ones handled at the set level.

    `concentration` and `rank_movement` compare members against each other rather than a
    member against its own past, so they cannot run over a single series.
    """
    out = []
    if "level_shift" in scope.detectors:
        detection = detectors.level_shift(series)
        if detection:
            out.append(detection)
    if "trend_break" in scope.detectors:
        detection = detectors.trend_break(series)
        if detection:
            out.append(detection)
    if "threshold" in scope.detectors:
        detection = detectors.threshold_breach(
            latest,
            watch_above=scope.watch_above, alert_above=scope.alert_above,
            watch_below=scope.watch_below, alert_below=scope.alert_below,
        )
        if detection:
            out.append(detection)
    return out


def _member_spec(spec: QuerySpec, dimension: str, member: str, cat: Catalog) -> QuerySpec:
    """The signal's evidence: the same series, filtered to the member that fired.

    Filtered on the raw code rather than the decoded label — the label is a display value,
    and a filter carrying it would match nothing.
    """
    from app.services.nlq.contracts import Filter

    kept = [f for f in spec.filters if f.field != dimension]
    return spec.model_copy(
        update={
            "filters": [*kept, Filter(field=dimension, op="eq", value=member)],
            "dimensions": [d for d in spec.dimensions if d != dimension],
        }
    )


def _signal(
    scope: SignalScope,
    metric,
    detection: detectors.Detection,
    spec: QuerySpec,
    cat: Catalog,
    *,
    member: str,
    value: float | None,
) -> Signal:
    subject = f"{humanize_label(metric.label)}"
    if member:
        subject = f"{subject} for {member}"
    reading = f" is {format_value(value, metric.unit)}" if value is not None else ""

    return Signal(
        scope=scope.id,
        label=scope.label if not member else f"{scope.label}: {member}",
        kind=detection.kind,
        metric=metric.id,
        dimension=scope.dimension or "",
        member=member,
        severity=detection.severity,  # type: ignore[arg-type]
        direction=detection.direction,  # type: ignore[arg-type]
        magnitude=detection.magnitude,
        baseline=detection.baseline,
        value=value,
        unit=metric.unit,  # type: ignore[arg-type]
        # Capitalised subject, then the detector's own words. Nothing here is generated: the
        # detector supplies the clause and the catalog supplies the label, so a signal cannot
        # describe a movement that did not happen.
        text=f"{subject[:1].upper()}{subject[1:]}{reading} — {detection.detail}.",
        spec=spec,
    )


# --------------------------------------------------------------------------------------
# Data health
# --------------------------------------------------------------------------------------


def _scan_data_health(cat: Catalog) -> tuple[list[Signal], list[str]]:
    """How fresh each source table is.

    This is the honest answer to "which data issues are affecting performance". A metric
    computed over a table that stopped loading four days ago is not wrong, it is stale, and
    every number derived from it is quietly about last Tuesday.
    """
    found: list[Signal] = []
    warnings: list[str] = []
    today = date.today()

    for check in cat.signals.data_health:
        table = cat.tables.get(check.table)
        if table is None:  # pragma: no cover - the catalog validator rejects these
            continue
        try:
            rows = execute(_freshness_query(table.table, check.date_column)).rows
        except ExecutionError as exc:
            logger.warning("freshness check on %s failed: %s", check.table, exc)
            warnings.append(f"Could not check how fresh {table.label} is.")
            continue

        newest = rows[0].get("newest") if rows else None
        days = (today - newest).days if isinstance(newest, date) else None
        detection = detectors.staleness(
            days, watch_days=check.watch_days, alert_days=check.alert_days
        )
        if detection is None:
            continue

        found.append(
            Signal(
                scope=f"data_health:{check.table}",
                label=f"{table.label} freshness",
                kind=detection.kind,
                severity=detection.severity,  # type: ignore[arg-type]
                direction="flat",
                magnitude=detection.magnitude,
                baseline=detection.baseline,
                unit="days",
                text=f"{table.label}: {detection.detail}."
                     + (f" {check.note}" if check.note else ""),
                # No spec: this is a finding about a table, not about a measure, and
                # attaching a plausible-looking query would send the reader to a chart that
                # cannot show them the problem.
                spec=None,
            )
        )
    return found, warnings


def _freshness_query(table: str, column: str) -> CompiledQuery:
    """One MAX(date) per table. Table and column come from the catalog, never from input."""
    return CompiledQuery(
        sql=f'SELECT MAX("{column}")::date AS newest FROM {table}',
        params={},
        source_tables=[table],
        metric_ids=[],
        dimension_ids=[],
        column_order=["newest"],
        formulas={},
    )


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

_SEVERITY_RANK = {"alert": 0, "watch": 1, "info": 2}


def _notability(signal: Signal) -> tuple[int, float]:
    return (_SEVERITY_RANK.get(signal.severity, 2), -abs(signal.magnitude))


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["MAX_WORKERS", "ScanError", "run"]
