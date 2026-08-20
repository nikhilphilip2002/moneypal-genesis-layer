"""Turning the catalog's early-warning rules into one query.

Every rule becomes a boolean column on the same scan, rather than a query each. Seven
predicates over 5,466 snapshot rows is one pass; seven queries is seven round trips and seven
chances for the account set to disagree with itself between them.

The SQL here is assembled entirely from `worklists.yaml`, which is reviewed and version
controlled — there is no user text in any predicate. The only values bound at runtime are the
as-of date, the row limit, and any dimension filters the caller supplied, all of which go
through named parameters exactly as the compiler does it.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.loader import EwsRule, WorklistConfig
from app.services.nlq.compiler import CompiledQuery
from app.services.nlq.contracts import Filter

RULE_PREFIX = "rule__"
"""Prefix for the boolean column each rule contributes, so a rule can never collide with a
selected data column."""

_EXPRESSION_REF = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

# The filters a worklist accepts. These are the slices a director actually asks for
# ("collections list for Aluva", "gold loans only"), and each maps to a column on the base
# relation. A dimension outside this map is refused rather than silently ignored — a
# worklist that quietly dropped its branch filter would send the wrong branch's accounts to
# a collections team.
FILTERABLE = {
    "branch": "s.branch_code",
    "product": "s.product_code",
    "scheme": "s.scheme_code",
    "asset_class": "s.asset_code",
    "agent": "l.agent_code",
    "borrower": "s.customer_name",
    "loan_account": "s.loan_account_number",
}


class RuleError(ValueError):
    """A worklist that cannot be built as asked."""


def compile_worklist(
    preset_id: str,
    *,
    catalog: Catalog | None = None,
    as_of: date | None = None,
    filters: list[Filter] | None = None,
    limit: int | None = None,
) -> tuple[CompiledQuery, tuple[EwsRule, ...]]:
    """Build the single scan behind a worklist, plus the rules it evaluates.

    Returns a `CompiledQuery` so the worklist runs through the same executor as everything
    else — same read-only role, same plan-cost gate, same result cache, same lineage. A
    second execution path would be a second place for the safety rails to be missing.
    """
    cat = catalog or get_catalog()
    config = cat.worklists
    preset = config.presets.get(preset_id)
    if preset is None:
        raise RuleError(f"unknown worklist {preset_id!r}")

    rules = tuple(config.rules[r] for r in preset.rules if r in config.rules)
    if not rules:
        raise RuleError(f"worklist {preset_id!r} has no usable rules")

    params: dict[str, Any] = {
        "as_of": as_of or date.today(),
        "row_limit": min(limit or preset.limit, 200),
    }

    selects = [f"{column.sql} AS {column.id}" for column in config.columns]
    selects += [
        f"({_expand(rule.predicate, config)}) AS {RULE_PREFIX}{rule.id}" for rule in rules
    ]

    where = [f"({_expand(rule.predicate, config)})" for rule in rules]
    predicate = " OR ".join(where)

    conditions = [f"({predicate})"]
    for index, filt in enumerate(filters or []):
        conditions.append(_filter_sql(filt, index, params))

    sql = (
        "SELECT " + ",\n       ".join(selects) + "\n"
        f"FROM {config.base_from} {config.base_alias}\n"
        + "".join(f"{join}\n" for join in config.joins)
        + "WHERE " + "\n  AND ".join(conditions) + "\n"
        # Ordered here only so the row cap is deterministic; the priority score is computed
        # in Python over the returned candidates and reorders them.
        "ORDER BY s.total_overdue DESC NULLS LAST, s.dpd_days DESC NULLS LAST\n"
        "LIMIT :row_limit"
    )

    return (
        CompiledQuery(
            sql=sql,
            params=params,
            source_tables=list(config.tables),
            metric_ids=[],
            dimension_ids=[c.id for c in config.columns],
            column_order=[c.id for c in config.columns],
            formulas={rule.id: rule.predicate for rule in rules},
            as_of=params["as_of"],
            period_label=f"As at {params['as_of']:%d %b %Y}",
            touches_pii=any(c.sensitivity == "pii" for c in config.columns),
        ),
        rules,
    )


def _expand(predicate: str, config: WorklistConfig) -> str:
    """Substitute named SQL fragments. Both sides come from the catalog file."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        fragment = config.expressions.get(name)
        if fragment is None:  # pragma: no cover - the catalog validator rejects these
            raise RuleError(f"predicate references undefined expression {{{name}}}")
        return f"({fragment})"

    return _EXPRESSION_REF.sub(replace, predicate)


def _filter_sql(filt: Filter, index: int, params: dict[str, Any]) -> str:
    """One caller-supplied slice, bound as a parameter rather than interpolated."""
    column = FILTERABLE.get(filt.field)
    if column is None:
        raise RuleError(
            f"a worklist cannot be filtered by {filt.field!r} — it is not a column on the "
            "account list"
        )
    name = f"wl_{index}"
    if filt.op == "eq":
        params[name] = filt.value
        return f"{column} = :{name}"
    if filt.op == "in":
        params[name] = list(filt.value) if isinstance(filt.value, list) else [filt.value]
        return f"{column} = ANY(:{name})"
    raise RuleError(f"a worklist filter cannot use {filt.op!r} — use 'eq' or 'in'")


def triggered_rules(row: dict[str, Any], rules: tuple[EwsRule, ...]) -> list[EwsRule]:
    """Which rules fired for this row, in the catalog's own severity order."""
    return [rule for rule in rules if row.get(f"{RULE_PREFIX}{rule.id}") is True]


__all__ = ["FILTERABLE", "RULE_PREFIX", "RuleError", "compile_worklist", "triggered_rules"]
