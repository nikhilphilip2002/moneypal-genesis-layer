"""AST allowlist for the text-to-SQL path (§2.6).

Parsed with sqlglot, not matched with regular expressions. A regex denylist is defeated by
comments, casing, unicode escapes and nesting; an AST walk sees the statement the database
will actually run.

**This is defence in depth, not the security boundary.** The boundary is the `nlq_readonly`
role, which holds SELECT on governed `gold.*` views. Every rule here is a second lock
on a door that is already locked — which is the right posture, because the thing on the
other side of it is an LLM following instructions that may have come from data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from app.services.nlq.catalog import Catalog, get_catalog

logger = logging.getLogger(__name__)

MAX_LIMIT = 5000
DIALECT = "postgres"

# Functions that read files, open sockets, or burn wall-clock. None has any legitimate use
# in a reporting query, and each is a documented exfiltration or DoS primitive.
BANNED_FUNCTIONS = {
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "dblink", "dblink_exec", "dblink_connect",
    "pg_sleep", "pg_sleep_for", "pg_sleep_until",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "query_to_xml", "xmlparse", "copy",
    "pg_read_server_files", "set_config", "current_setting",
    "pg_logical_emit_message", "pg_create_physical_replication_slot",
}

# Schemas whose mere presence in a query is a probe.
BANNED_SCHEMAS = {
    "pg_catalog", "information_schema", "pg_toast", "bronze", "public", "silver"
}


class ValidationError(ValueError):
    """A statement the validator refuses. The reason is logged and fed back to the model
    for its single repair attempt — but never shown verbatim to the user, because the
    message names tables and would leak schema."""


@dataclass(slots=True)
class ValidationResult:
    sql: str
    tables: list[str] = field(default_factory=list)
    pii_columns: list[str] = field(default_factory=list)
    limit_injected: bool = False
    warnings: list[str] = field(default_factory=list)


def validate(
    sql: str,
    *,
    catalog: Catalog | None = None,
    allow_pii: bool = False,
    allowed_pii_columns: set[str] | None = None,
    max_limit: int = MAX_LIMIT,
) -> ValidationResult:
    """Parse and check a generated statement. Returns the (possibly rewritten) SQL."""
    cat = catalog or get_catalog()

    statements = _parse(sql)
    _check_single_statement(statements)
    tree = statements[0]

    _check_is_select(tree)
    _check_no_write_ctes(tree)
    _check_no_star(tree)
    _check_functions(tree)
    _check_no_set_operations_on_forbidden_tables(tree, cat)
    tables = _check_tables(tree, cat)
    _check_columns(tree, cat)
    _check_joins_have_conditions(tree)
    pii = _check_pii(tree, cat, allow_pii, allowed_pii_columns)
    tree, injected = _enforce_limit(tree, max_limit)

    return ValidationResult(
        sql=tree.sql(dialect=DIALECT, pretty=True),
        tables=sorted(tables),
        pii_columns=sorted(pii),
        limit_injected=injected,
    )


# --------------------------------------------------------------------------------------
# Individual rules
# --------------------------------------------------------------------------------------


def _parse(sql: str) -> list[exp.Expression]:
    if not sql or not sql.strip():
        raise ValidationError("empty statement")
    try:
        parsed = sqlglot.parse(sql, read=DIALECT)
    except Exception as exc:  # noqa: BLE001 - sqlglot raises several types
        raise ValidationError(f"could not be parsed as PostgreSQL: {exc}") from exc
    statements = [s for s in parsed if s is not None]
    if not statements:
        raise ValidationError("no statement found")
    return statements


def _check_single_statement(statements: list[exp.Expression]) -> None:
    """Blocks `SELECT 1; DROP TABLE x` stacking."""
    if len(statements) > 1:
        raise ValidationError(
            f"{len(statements)} statements found; exactly one SELECT is allowed"
        )


def _check_is_select(tree: exp.Expression) -> None:
    """Root must be a SELECT (or a union of them). Rejects every DDL and DML form."""
    if isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return
    if isinstance(tree, exp.Subquery):
        return
    if isinstance(tree, exp.With) and isinstance(tree.this, (exp.Select, exp.Union)):
        return
    raise ValidationError(
        f"root node is {type(tree).__name__}; only SELECT statements are allowed"
    )


def _check_no_write_ctes(tree: exp.Expression) -> None:
    """The classic read-only bypass: `WITH x AS (DELETE ... RETURNING *) SELECT * FROM x`.

    Postgres executes data-modifying CTEs, so a statement whose root is a SELECT can still
    write. The role's missing privileges would stop it, but this must not depend on that.
    """
    for node in tree.walk():
        if isinstance(
            node,
            (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop,
             exp.Alter, exp.TruncateTable),
        ):
            raise ValidationError(
                f"contains a {type(node).__name__.upper()} operation; the NLQ path is read-only"
            )


def _check_no_star(tree: exp.Expression) -> None:
    """`SELECT *` is uncontrolled PII egress — a customer table has 56 columns."""
    for node in tree.find_all(exp.Star):
        raise ValidationError("SELECT * is not allowed; name the columns explicitly")
    for node in tree.find_all(exp.Column):
        if isinstance(node.this, exp.Star):
            raise ValidationError("table.* is not allowed; name the columns explicitly")


def _check_functions(tree: exp.Expression) -> None:
    for node in tree.find_all(exp.Anonymous):
        name = str(node.this).lower() if node.this else ""
        if name in BANNED_FUNCTIONS:
            raise ValidationError(f"function {name}() is not permitted")
    # Named function nodes sqlglot models explicitly rather than as Anonymous.
    for node in tree.walk():
        key = getattr(node, "key", "")
        if isinstance(key, str) and key.lower() in BANNED_FUNCTIONS:
            raise ValidationError(f"function {key.lower()}() is not permitted")


def _check_tables(tree: exp.Expression, catalog: Catalog) -> set[str]:
    """Every table must be in the catalog's governed Gold-view allowlist.

    CTE names are resolved first so a query's own `WITH` aliases are not mistaken for
    unknown tables.
    """
    allowed = catalog.allowed_tables()
    cte_names = {
        (cte.alias_or_name or "").lower() for cte in tree.find_all(exp.CTE)
    }

    found: set[str] = set()
    for table in tree.find_all(exp.Table):
        name = (table.name or "").lower()
        schema = (table.db or "").lower()

        if not schema and name in cte_names:
            continue  # a reference to this query's own CTE

        if schema in BANNED_SCHEMAS:
            raise ValidationError(f"schema {schema!r} is not accessible")
        if not schema:
            raise ValidationError(
                f"table {name!r} is not schema-qualified; use gold.<view>"
            )

        qualified = f"{schema}.{name}"
        if qualified not in allowed:
            raise ValidationError(f"table {qualified!r} is not in the allowlist")
        found.add(qualified)

    if not found:
        raise ValidationError("no known table is referenced")
    return found


def _physical_columns(catalog: Catalog) -> dict[str, set[str]]:
    """Columns the generated-SQL path may reference, keyed by qualified table.

    The curated column catalog supplies business fields. Table keys/date fields and the
    declared join endpoints are also real columns exposed in the prompt's join paths.
    Anything else is an invention and must be rejected before EXPLAIN reaches Postgres.
    """
    allowed = {table.table: set(table.key) for table in catalog.tables.values()}
    for table in catalog.tables.values():
        allowed[table.table].update(table.date_columns.values())
        if table.as_of_column:
            allowed[table.table].add(table.as_of_column)
        if table.year_column:
            allowed[table.table].add(table.year_column)
    for column in catalog.columns.values():
        allowed.setdefault(column.table, set()).add(column.column)
    for dimension in catalog.dimensions.values():
        if dimension.table and dimension.column:
            allowed.setdefault(dimension.table, set()).add(dimension.column)
    for join in catalog.joins:
        for left_column, right_column in join.on:
            allowed.setdefault(join.left, set()).add(left_column)
            allowed.setdefault(join.right, set()).add(right_column)
    return {table: {column.lower() for column in columns} for table, columns in allowed.items()}


def _check_columns(tree: exp.Expression, catalog: Catalog) -> None:
    """Reject hallucinated physical column names before the database sees the query."""
    allowed = _physical_columns(catalog)
    aliases: dict[str, str] = {}
    derived_aliases: set[str] = set()

    for table in tree.find_all(exp.Table):
        qualified = f"{(table.db or '').lower()}.{(table.name or '').lower()}"
        if qualified in allowed:
            aliases[(table.alias_or_name or table.name or "").lower()] = qualified

    derived_aliases.update(
        (cte.alias_or_name or "").lower() for cte in tree.find_all(exp.CTE)
    )
    derived_aliases.update(
        (subquery.alias_or_name or "").lower()
        for subquery in tree.find_all(exp.Subquery)
        if subquery.alias_or_name
    )
    derived_aliases.update(
        (lateral.alias_or_name or "").lower()
        for lateral in tree.find_all(exp.Lateral)
        if lateral.alias_or_name
    )
    output_aliases = {
        (alias.alias or "").lower() for alias in tree.find_all(exp.Alias) if alias.alias
    }
    all_physical = set().union(*allowed.values()) if allowed else set()

    for column in tree.find_all(exp.Column):
        name = (column.name or "").lower()
        qualifier = (column.table or "").lower()
        if not name or name in output_aliases:
            continue
        if qualifier in derived_aliases:
            continue
        if qualifier:
            table_name = aliases.get(qualifier)
            if table_name is None:
                raise ValidationError(f"column qualifier {qualifier!r} is not a known table alias")
            if name not in allowed[table_name]:
                raise ValidationError(f"column {name!r} does not exist on {table_name}")
        elif name not in all_physical:
            raise ValidationError(f"column {name!r} is not in the catalog allowlist")


def _check_no_set_operations_on_forbidden_tables(tree: exp.Expression, catalog: Catalog) -> None:
    """A UNION arm is a whole second query and gets the same scrutiny as the first —
    `SELECT a FROM gold.x UNION SELECT rolpassword FROM pg_authid` must not slip past a
    check that only looked at the leading SELECT."""
    for node in tree.find_all(exp.Union, exp.Intersect, exp.Except):
        for side in (node.left, node.right):
            if side is not None:
                _check_no_star(side)


def _check_joins_have_conditions(tree: exp.Expression) -> None:
    """A missing ON clause is a cartesian product: 13k accounts x 260k schedule rows is
    3.5 billion rows, which is a denial of service written by accident."""
    for join in tree.find_all(exp.Join):
        if join.args.get("on") or join.args.get("using"):
            continue
        # sqlglot puts CROSS in `kind`, not `side` — reading only `side` would reject the
        # compiler's own point-in-time series, which is a legitimate correlated lateral.
        kind = (join.kind or join.side or "").upper()
        if kind == "CROSS" and isinstance(join.this, (exp.Lateral, exp.Subquery)):
            continue  # correlated by construction, not a cartesian product
        raise ValidationError(
            "a join has no ON condition, which would produce a cartesian product"
        )


def _check_pii(
    tree: exp.Expression,
    catalog: Catalog,
    allow_pii: bool,
    allowed_pii_columns: set[str] | None = None,
) -> set[str]:
    """Find referenced PII columns; reject them when the caller's role does not permit."""
    pii_columns = {column for _table, column in catalog.pii_columns()}
    referenced = {
        (column.name or "").lower()
        for column in tree.find_all(exp.Column)
        if (column.name or "").lower() in pii_columns
    }
    if referenced and not allow_pii:
        raise ValidationError(
            f"references restricted columns ({', '.join(sorted(referenced))}) that this "
            "role may not read"
        )
    if referenced and allowed_pii_columns is not None:
        allowed = {column.lower() for column in allowed_pii_columns}
        forbidden = referenced - allowed
        if forbidden:
            raise ValidationError(
                f"references restricted columns ({', '.join(sorted(forbidden))}) that are "
                "not permitted for this query path"
            )
    return referenced


def _enforce_limit(tree: exp.Expression, max_limit: int) -> tuple[exp.Expression, bool]:
    """Ensure a bounded result set, injecting a LIMIT when one is absent."""
    select = tree.this if isinstance(tree, exp.With) else tree
    if not isinstance(select, (exp.Select, exp.Union)):
        return tree, False

    limit = select.args.get("limit")
    if limit is None:
        return tree.limit(max_limit), True

    try:
        value = int(limit.expression.this)
    except (AttributeError, TypeError, ValueError):
        raise ValidationError("LIMIT must be a literal integer") from None

    if value > max_limit:
        raise ValidationError(f"LIMIT {value} exceeds the maximum of {max_limit}")
    return tree, False


def is_safe(sql: str, **kwargs) -> bool:
    """Boolean form, for tests and quick checks."""
    try:
        validate(sql, **kwargs)
        return True
    except ValidationError:
        return False
