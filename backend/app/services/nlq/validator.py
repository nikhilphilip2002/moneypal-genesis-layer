"""AST allowlist for SQL accepted by the PostgreSQL MCP boundary.

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
import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, ScopeType, traverse_scope

from app.core.config import settings
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

# Functions a reporting query legitimately needs, named as PostgreSQL spells them. In
# `allowlist` mode (NLQ_SQL_FUNCTION_MODE) anything outside this set is rejected; in the
# default `denylist` mode an unlisted function is logged at INFO so the list can be completed
# from canary evidence before the switch is flipped. Seeded from what the QuerySpec compiler,
# the lookup module and the validator's own tests already emit.
ALLOWED_FUNCTIONS = {
    # aggregates and window functions
    "count", "sum", "avg", "min", "max", "string_agg", "array_agg", "bool_and", "bool_or",
    "every", "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop", "var_samp", "corr",
    "percentile_cont", "percentile_disc", "row_number", "rank", "dense_rank", "percent_rank",
    "ntile", "lag", "lead", "first_value", "last_value", "nth_value",
    # null handling, conditionals, casts ("if" is how sqlglot models a CASE ... WHEN arm)
    "coalesce", "nullif", "greatest", "least", "case", "if", "cast", "exists", "array",
    # arithmetic
    "round", "trunc", "abs", "floor", "ceil", "ceiling", "sign", "mod", "div", "power",
    "sqrt", "ln", "log", "exp", "width_bucket",
    # dates
    "date_trunc", "date_part", "extract", "to_char", "to_date", "to_timestamp", "make_date",
    "make_interval", "age", "now", "current_date", "current_timestamp", "current_time",
    "localtimestamp", "date_bin", "justify_days", "justify_interval", "isfinite",
    "generate_series",
    # strings
    "lower", "upper", "trim", "ltrim", "rtrim", "btrim", "initcap", "concat", "concat_ws",
    "substring", "substr", "left", "right", "length", "char_length", "replace", "split_part",
    "strpos", "position", "lpad", "rpad", "regexp_replace", "regexp_matches", "to_number",
    # arrays
    "unnest", "array_to_string", "array_length", "cardinality",
}

FUNCTION_MODES = ("denylist", "allowlist")

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
    function_mode: str | None = None,
) -> ValidationResult:
    """Parse and check a generated statement. Returns the (possibly rewritten) SQL.

    `function_mode` is `denylist` or `allowlist`; when omitted it comes from
    `settings.nlq_sql_function_mode`.
    """
    cat = catalog or get_catalog()
    mode = (function_mode or settings.nlq_sql_function_mode or "denylist").lower()
    if mode not in FUNCTION_MODES:
        raise ValueError(f"unknown function mode {mode!r}; expected one of {FUNCTION_MODES}")

    statements = _parse(sql)
    _check_single_statement(statements)
    tree = statements[0]

    _check_is_select(tree)
    _check_no_write_ctes(tree)
    _check_no_star(tree)
    _check_functions(tree, mode)
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


_FUNCTION_CALL_NAME = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\(")
_BARE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _function_names(node: exp.Func) -> tuple[str, set[str]]:
    """The names a function node answers to: how PostgreSQL spells it, plus sqlglot's own
    canonical key (sqlglot parses `DATE_TRUNC` into `TimestampTrunc` and `TO_CHAR` into
    `TimeToStr`; the rendered form is what the allowlist is written against).

    Returns (display name, all lowercase candidates)."""
    candidates: set[str] = set()
    display = ""
    if isinstance(node, exp.Anonymous):
        display = (node.name or "").lower()
        candidates.add(display)
    else:
        try:
            rendered = node.sql(dialect=DIALECT)
        except Exception:  # noqa: BLE001 - never let a rendering quirk skip the check
            rendered = ""
        match = _FUNCTION_CALL_NAME.match(rendered)
        if match:
            display = match.group(1).lower()
        elif _BARE_NAME.match(rendered.strip()):
            display = rendered.strip().lower()
        if display:
            candidates.add(display)
        candidates.add(str(node.key).lower())
        candidates.add(node.sql_name().lower())
        display = display or str(node.key).lower()
    return display, {name for name in candidates if name}


def _check_functions(tree: exp.Expression, mode: str = "denylist") -> None:
    """The denylist always applies. In `allowlist` mode any function outside
    ALLOWED_FUNCTIONS is rejected; in `denylist` mode it is logged so the allowlist can be
    completed from evidence before the mode is switched."""
    for node in tree.walk():
        # sqlglot models AND/OR/NOT and the comparison operators as Func subclasses too;
        # they are syntax, not callables, and only the callable form is policed here.
        operator = isinstance(node, (exp.Binary, exp.Unary, exp.Predicate))
        if isinstance(node, exp.Func) and not operator:
            display, names = _function_names(node)
            if names & BANNED_FUNCTIONS:
                raise ValidationError(f"function {display}() is not permitted")
            if names & ALLOWED_FUNCTIONS:
                continue
            if mode == "allowlist":
                raise ValidationError(f"function {display}() is not on the allowlist")
            logger.info("NLQ validator saw function %s() outside the allowlist", display)
            continue
        # Non-function nodes sqlglot models explicitly, e.g. COPY.
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
    """Reject hallucinated physical column names before the database sees the query.

    Resolution is per scope, using sqlglot's scope tree (`traverse_scope`): an unqualified
    column is looked up in the sources of the SELECT it appears in, then in enclosing
    scopes (a correlated reference), and is ambiguous only when two sources of the *same*
    scope carry it. A subquery or UNION arm reading another Gold view therefore does not
    make the outer SELECT ambiguous. A qualifier naming a CTE, derived table or lateral
    resolves to that scope's projected column list, so `WITH c AS (...) SELECT c.made_up
    FROM c` is rejected rather than skipped.

    sqlglot's own `Scope.columns` is not used because it assumes `qualify_columns` has run
    and treats every unqualified column as external; ownership is decided here by walking
    each Column up to the nearest scope expression.
    """
    allowed = _physical_columns(catalog)

    root = tree
    while isinstance(root, (exp.Subquery, exp.Paren)):
        root = root.this
    try:
        scopes = traverse_scope(root)
    except Exception as exc:  # noqa: BLE001 - sqlglot raises several types
        raise ValidationError(f"could not resolve query scopes: {exc}") from exc
    if not scopes:
        raise ValidationError("no query scope found")
    scope_by_expression = {id(scope.expression): scope for scope in scopes}

    for column in root.find_all(exp.Column):
        name = (column.name or "").lower()
        if not name:
            continue
        scope = _owning_scope(column, scope_by_expression) or scopes[-1]
        qualifier = (column.table or "").lower()
        if qualifier:
            _resolve_qualified(name, qualifier, scope, allowed)
        else:
            _resolve_unqualified(name, scope, allowed)


def _owning_scope(column: exp.Column, scope_by_expression: dict[int, Scope]) -> Scope | None:
    node = column.parent
    while node is not None:
        scope = scope_by_expression.get(id(node))
        if scope is not None:
            return scope
        node = node.parent
    return None


def _scope_sources(scope: Scope) -> dict[str, exp.Table | Scope]:
    return {
        (alias or "").lower(): source
        for alias, source in scope.sources.items()
        if alias and isinstance(source, (exp.Table, Scope))
    }


def _projected_columns(
    source: exp.Table | Scope, allowed: dict[str, set[str]]
) -> set[str] | None:
    """Columns a FROM-clause source exposes, or None when they cannot be determined."""
    if isinstance(source, exp.Table):
        alias = source.args.get("alias")
        if alias is not None and alias.columns:
            return {(c.name or "").lower() for c in alias.columns}
        qualified = f"{(source.db or '').lower()}.{(source.name or '').lower()}"
        return allowed.get(qualified)

    expression = source.expression
    alias = expression.args.get("alias")
    if alias is not None and getattr(alias, "columns", None):
        return {(c.name or "").lower() for c in alias.columns}
    while isinstance(expression, (exp.Lateral, exp.Subquery, exp.Paren)):
        expression = expression.this
    if isinstance(expression, (exp.Select, exp.SetOperation)):
        return {n.lower() for n in expression.named_selects if n}
    return None


def _source_label(alias: str, source: exp.Table | Scope) -> str:
    if isinstance(source, exp.Table):
        return f"{(source.db or '').lower()}.{(source.name or '').lower()}"
    return alias


def _describe_scope(scope: Scope) -> str:
    kind = scope.scope_type
    expression = scope.expression
    if kind == ScopeType.ROOT:
        return "the outer query"
    if kind == ScopeType.CTE:
        parent = expression.parent
        alias = parent.alias_or_name if isinstance(parent, exp.CTE) else ""
        return f"CTE {alias!r}" if alias else "a CTE"
    if kind == ScopeType.DERIVED_TABLE:
        parent = expression.parent
        alias = parent.alias_or_name if isinstance(parent, exp.Subquery) else ""
        return f"derived table {alias!r}" if alias else "a derived table"
    if kind == ScopeType.UNION:
        return "a UNION branch"
    if kind == ScopeType.SUBQUERY:
        return "a subquery"
    if kind == ScopeType.UDTF:
        return "a lateral"
    return "a query scope"


def _resolve_qualified(
    name: str, qualifier: str, scope: Scope, allowed: dict[str, set[str]]
) -> None:
    current: Scope | None = scope
    while current is not None:
        source = _scope_sources(current).get(qualifier)
        if source is not None:
            projected = _projected_columns(source, allowed)
            if projected is None:
                raise ValidationError(
                    f"columns of {qualifier!r} cannot be determined; use a SELECT with "
                    "named columns"
                )
            if name not in projected:
                if isinstance(source, exp.Table):
                    raise ValidationError(
                        f"column {name!r} does not exist on {_source_label(qualifier, source)}"
                    )
                raise ValidationError(
                    f"column {name!r} is not projected by {qualifier!r} "
                    f"(available: {', '.join(sorted(projected))})"
                )
            return
        current = current.parent
    raise ValidationError(
        f"column qualifier {qualifier!r} is not a known table alias in "
        f"{_describe_scope(scope)}"
    )


def _resolve_unqualified(name: str, scope: Scope, allowed: dict[str, set[str]]) -> None:
    expression = scope.expression
    # A select-list alias may be referenced from GROUP BY / ORDER BY of the same SELECT,
    # and a set operation's ORDER BY names the union's output columns.
    if isinstance(expression, exp.Select):
        output_aliases = {
            (a.alias or "").lower() for a in expression.expressions if isinstance(a, exp.Alias)
        }
        if name in output_aliases:
            return
    elif isinstance(expression, exp.SetOperation):
        if name in {n.lower() for n in expression.named_selects if n}:
            return

    current: Scope | None = scope
    while current is not None:
        matching = [
            _source_label(alias, source)
            for alias, source in _scope_sources(current).items()
            if (projected := _projected_columns(source, allowed)) is not None
            and name in projected
        ]
        if len(matching) > 1:
            raise ValidationError(
                f"column {name!r} is ambiguous across referenced tables in "
                f"{_describe_scope(current)} ({', '.join(sorted(matching))}); qualify it"
            )
        if matching:
            return
        current = current.parent
    raise ValidationError(
        f"column {name!r} does not exist on any referenced table in {_describe_scope(scope)}"
    )


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
