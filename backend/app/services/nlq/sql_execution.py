"""Shared types and metadata helpers for governed, already-validated SQL.

This module does not generate SQL. Fixed record lookups construct statements in application
code, while PostgreSQL MCP validates model-authored statements at its own boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import sqlglot
from sqlglot import exp

from app.services.nlq.catalog import Catalog
from app.services.nlq.contracts import Lineage


@dataclass(slots=True)
class ValidatedSql:
    sql: str = ""
    tables: list[str] = field(default_factory=list)
    explanation: str = ""
    validated: bool = False
    warnings: list[str] = field(default_factory=list)
    column_units: dict[str, str] = field(default_factory=dict)


def infer_column_units(sql: str, tables: list[str], catalog: Catalog) -> dict[str, str]:
    """Carry catalog units through SQL aliases such as ``total_security_value``."""
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except Exception:  # pragma: no cover - validated SQL has already parsed successfully
        return {}

    units_by_name: dict[str, set[str]] = {}
    for table in tables:
        for column in catalog.columns_for(table):
            units_by_name.setdefault(column.column.lower(), set()).add(column.unit)

    inferred: dict[str, str] = {}
    select = tree.find(exp.Select)
    if select is None:
        return inferred
    for expression in select.expressions:
        output_name = expression.alias_or_name
        if not output_name:
            continue
        if expression.find(exp.Count) is not None:
            inferred[output_name] = "count"
            continue
        source_units = {
            unit
            for column in expression.find_all(exp.Column)
            for unit in units_by_name.get(column.name.lower(), set())
        }
        if len(source_units) == 1:
            inferred[output_name] = source_units.pop()
    return inferred


def lineage_for_validated_sql(
    statement: ValidatedSql, row_count: int, duration_ms: int,
) -> Lineage:
    """Lineage for deterministic application-owned SQL used by record lookups."""
    return Lineage(
        path="validated_sql",
        sql=statement.sql,
        display_sql=statement.sql,
        parameters={},
        source_tables=statement.tables,
        formulas={},
        row_count=row_count,
        duration_ms=duration_ms,
        warnings=list(statement.warnings),
        unverified=False,
    )
