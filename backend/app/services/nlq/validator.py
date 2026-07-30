"""AST allowlist for the text-to-SQL path (§2.6).

Parsed with sqlglot, not matched with regular expressions. A regex denylist is defeated by
comments, casing, unicode escapes and nesting; an AST walk sees the statement the database
will actually run.

**This is defence in depth, not the security boundary.** The boundary is the `nlq_readonly`
role, which holds SELECT on `silver.*` and nothing else. Every rule here is a second lock
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
BANNED_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast", "bronze", "public"}


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
    _check_joins_have_conditions(tree)
    pii = _check_pii(tree, cat, allow_pii)
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
    """Every table must be in the catalog's silver allowlist.

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
                f"table {name!r} is not schema-qualified; use silver.<table>"
            )

        qualified = f"{schema}.{name}"
        if qualified not in allowed:
            raise ValidationError(f"table {qualified!r} is not in the allowlist")
        found.add(qualified)

    if not found:
        raise ValidationError("no known table is referenced")
    return found


def _check_no_set_operations_on_forbidden_tables(tree: exp.Expression, catalog: Catalog) -> None:
    """A UNION arm is a whole second query and gets the same scrutiny as the first —
    `SELECT a FROM silver.x UNION SELECT rolpassword FROM pg_authid` must not slip past a
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


def _check_pii(tree: exp.Expression, catalog: Catalog, allow_pii: bool) -> set[str]:
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
