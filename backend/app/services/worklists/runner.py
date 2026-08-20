"""Compile → execute → rank → explain. The whole worklist, in one call.

The execution goes through the ordinary NLQ executor, so a worklist inherits the read-only
role, the plan-cost gate, the result cache and the lineage panel without any of them being
re-implemented. A second execution path would be a second place for a safety rail to be
missing, and this is the surface that ends in someone phoning a borrower.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Any, Iterable

from app.services.nlq import pii
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.loader import EwsRule, WorklistPreset, canonical_enum_code
from app.services.nlq.compiler import describe_parameters, render_sql_for_display
from app.services.nlq.contracts import (
    ColumnSpec,
    Filter,
    Lineage,
    Worklist,
    WorklistItem,
)
from app.services.nlq.executor import execute
from app.services.nlq.narrator import format_value
from app.services.worklists import rules as rule_engine
from app.services.worklists.score import prioritise

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"alert": 0, "watch": 1, "info": 2}


class WorklistError(ValueError):
    """A worklist that cannot be built or answered."""


def presets(catalog: Catalog | None = None) -> Iterable[WorklistPreset]:
    return (catalog or get_catalog()).worklists.presets.values()


def build(
    worklist_id: str,
    *,
    catalog: Catalog | None = None,
    as_of: date | None = None,
    filters: list[Filter] | None = None,
    limit: int | None = None,
    role: str | None = None,
) -> Worklist:
    """Run a worklist preset and return the ranked, explained list."""
    cat = catalog or get_catalog()
    config = cat.worklists
    preset = config.presets.get(worklist_id)
    if preset is None:
        raise WorklistError(f"unknown worklist {worklist_id!r}")

    try:
        compiled, active_rules = rule_engine.compile_worklist(
            worklist_id, catalog=cat, as_of=as_of, filters=filters, limit=limit
        )
    except rule_engine.RuleError as exc:
        raise WorklistError(str(exc)) from exc

    result = execute(compiled)
    rows = [_decode(row, cat) for row in result.rows]
    items = _rank(rows, active_rules, cat)

    lineage = Lineage(
        path="queryspec",
        sql=result.sql,
        display_sql=render_sql_for_display(compiled.sql, compiled.params),
        parameters=describe_parameters(compiled.params),
        source_tables=compiled.source_tables,
        # The rule predicates *are* the formulas here: the lineage panel should show why an
        # account qualified, not only where the numbers came from.
        formulas={
            **compiled.formulas,
            "priority score": " + ".join(
                f"{c.weight} x {c.label} (percentile rank)" for c in config.score.components
            ),
        },
        row_count=len(items),
        duration_ms=result.duration_ms,
        as_of=compiled.as_of,
        warnings=list(result.warnings),
    )

    worklist = Worklist(
        id=preset.id,
        title=preset.title,
        subtitle=compiled.period_label,
        as_of=compiled.as_of,
        method=config.score.method,
        columns=_columns(cat),
        items=items,
        candidate_count=result.row_count,
        lineage=lineage,
        warnings=_warnings(result, preset, len(items)),
        unavailable=[
            f"{entry.get('rule', 'A rule')} — needs {entry.get('needs', 'data we do not hold')}"
            for entry in config.unavailable
        ],
    )
    return _mask(worklist, role, cat)


# --------------------------------------------------------------------------------------
# Ranking and explanation
# --------------------------------------------------------------------------------------


def _rank(
    rows: list[dict[str, Any]], active_rules: tuple[EwsRule, ...], cat: Catalog
) -> list[WorklistItem]:
    scored = prioritise(rows, cat.worklists.score)
    items: list[WorklistItem] = []

    for row, (score, weights) in zip(rows, scored):
        triggered = rule_engine.triggered_rules(row, active_rules)
        if not triggered:
            # The WHERE clause is the OR of the same predicates, so this cannot normally
            # happen. If it does, the row has no reason to be on a worklist and stating one
            # would be an invention.
            continue
        severity = min((r.severity for r in triggered), key=lambda s: _SEVERITY_RANK.get(s, 2))
        playbook = cat.worklists.playbook_for(
            row.get("asset_class__raw", row.get("asset_class")), row.get("dpd_days")
        )
        items.append(
            WorklistItem(
                rank=0,  # assigned after the sort, so it always matches what is displayed
                account=canonical_enum_code(row.get("loan_account_number", "")),
                score=score,
                severity=severity,  # type: ignore[arg-type]
                reasons=[_reason(rule, row, cat) for rule in triggered],
                triggered=[rule.id for rule in triggered],
                action=playbook.action if playbook else "",
                owner=playbook.owner if playbook else "",
                weights=weights,
                fields=_display_fields(row),
            )
        )

    # Severity first, then score. An alert scoring 0.71 belongs above a watch scoring 0.78:
    # the score orders accounts within a class of problem, it does not compare classes.
    items.sort(key=lambda i: (_SEVERITY_RANK.get(i.severity, 2), -i.score))
    for position, item in enumerate(items, start=1):
        item.rank = position
    return items


def _reason(rule: EwsRule, row: dict[str, Any], cat: Catalog) -> str:
    """The rule's sentence with this row's values in it.

    Values are formatted the way the rest of the product formats them — ₹2.4L, not
    240000.0 — because a reason a person has to decode is a reason they skip.
    """
    if not rule.reason:
        return rule.label
    text = rule.reason
    for column in cat.worklists.columns:
        token = "{" + column.id + "}"
        if token not in text:
            continue
        value = row.get(column.id)
        rendered = "not recorded" if value is None else format_value(value, column.unit)
        text = text.replace(token, str(rendered))
    return text


def _decode(row: dict[str, Any], cat: Catalog) -> dict[str, Any]:
    """Codes to labels, keeping the raw code alongside for filters and playbook matching."""
    out = dict(row)
    for column in cat.worklists.columns:
        if not column.decode or column.id not in row:
            continue
        enum = cat.enums.get(column.decode)
        raw = row[column.id]
        if enum is None or raw is None:
            continue
        out[f"{column.id}__raw"] = canonical_enum_code(raw)
        out[column.id] = enum.label_for(raw)
    return out


def _display_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Everything except the rule booleans and the raw codes behind decoded labels.

    The account number is an identifier that Postgres hands back as `numeric`, so it arrives
    as a float and renders as "1000400003373.0". An officer reading that off a screen to key
    into the core system has to know to drop the ".0", which is exactly the kind of small
    friction that gets a list abandoned."""
    out = {
        key: value
        for key, value in row.items()
        if not key.startswith(rule_engine.RULE_PREFIX) and not key.endswith("__raw")
    }
    if "loan_account_number" in out:
        out["loan_account_number"] = canonical_enum_code(out["loan_account_number"])
    return out


def _columns(cat: Catalog) -> list[ColumnSpec]:
    return [
        ColumnSpec(
            name=column.id,
            label=column.label,
            unit=column.unit,  # type: ignore[arg-type]
            sensitivity=column.sensitivity,  # type: ignore[arg-type]
        )
        for column in cat.worklists.columns
    ]


def _warnings(result, preset: WorklistPreset, shown: int) -> list[str]:
    warnings: list[str] = []
    if result.truncated:
        warnings.append(
            f"More accounts qualified than the {preset.limit} shown. Narrow by branch or "
            "product to see the rest."
        )
    if not shown:
        warnings.append("No account triggered any of this list's rules for the requested slice.")
    return warnings


def _mask(worklist: Worklist, role: str | None, cat: Catalog) -> Worklist:
    """Mask PII unless the caller's role permits it, exactly as a chart does.

    A worklist is the most PII-dense surface in the product — it is a list of named
    borrowers — so this is not optional and is not left to the caller.
    """
    rows = [item.fields for item in worklist.items]
    masked_rows, masked = pii.mask_rows(rows, worklist.columns, role=role, catalog=cat)
    if not masked:
        return worklist
    for item, row in zip(worklist.items, masked_rows):
        item.fields = row
    for column in worklist.columns:
        if column.name in masked:
            column.masked = True
    worklist.lineage.warnings.append(
        f"Masked for your role: {', '.join(sorted(masked))}."
    )
    return worklist


# --------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------


def to_csv(worklist: Worklist) -> str:
    """The list as a spreadsheet, because that is how it reaches a branch.

    The reason and the action travel with each row. A CSV of account numbers with no reason
    is a list somebody has to re-derive before they can use it, which means they will not.
    """
    buffer = io.StringIO()
    headers = [
        "rank", "account", "severity", "score",
        *[column.name for column in worklist.columns if column.name != "loan_account_number"],
        "reasons", "action", "owner",
    ]
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for item in worklist.items:
        writer.writerow({
            "rank": item.rank,
            "account": item.account,
            "severity": item.severity,
            "score": item.score,
            **item.fields,
            "reasons": " ".join(item.reasons),
            "action": item.action,
            "owner": item.owner,
        })
    return buffer.getvalue()


__all__ = ["WorklistError", "build", "presets", "to_csv"]
