"""Text-to-SQL fallback, for the long tail the catalog does not cover (§2.6).

Reached only on a catalog miss. Everything about this path is more cautious than the
QuerySpec path, because the model is writing the statement rather than filling in a form:

* the generation prompt carries real DDL for the retrieved tables, not a paraphrase;
* the output goes through `validator.py` before it can reach a cursor, with exactly one
  repair round-trip and then a refusal;
* the EXPLAIN cost gate in the executor runs before any rows are read;
* the answer is marked `unverified` so the UI can say so.

Preferring a refusal over a low-confidence answer is the policy here. A plausible-but-wrong
result on this path damages trust more than an honest "I could not answer that", because
the user has no way to tell the two apart.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from app.core.config import settings
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.contracts import Lineage
from app.services.nlq.llm import LLMError, get_llm_client
from app.services.nlq.llm.prompts import catalog_block
from app.services.nlq.llm.schemas import sql_schema
from app.services.nlq.llm.telemetry import stable_hash
from app.services.nlq.validator import ValidationError, validate

logger = logging.getLogger(__name__)

SQL_PROMPT_VERSION = "sql-v3-qualified-columns"

SYSTEM_PROMPT = """\
You write a single PostgreSQL SELECT statement answering the user's question about a \
lending book. You output JSON only.

HARD RULES — a statement breaking any of these is discarded:
- Exactly one SELECT statement. No semicolons, no DDL, no DML, no CTE that writes.
- Schema-qualify every source as gold.<view>. Never reference bronze, silver, public, \
pg_catalog or information_schema.
- Never use SELECT * or table.*. Name every column.
- Every join must have an explicit ON condition.
- Always include a LIMIT of at most 5000.
- Always bound the query with a date filter when the table has a date column.
- Never reference a column that is not listed in the schema below.
- Qualify every column with its table alias when more than one table appears \
anywhere in the statement, including in subqueries, CTEs and UNION branches.
{pii_rule}

DOMAIN
- Indian financial year runs 1 April to 31 March.
- Account keys are compound: every join must include entity_num as well as the account \
number, or rows from two entities will be merged.
- Gold views are the governed semantic layer. Historical portfolio questions belong on \
the reviewed QuerySpec path; generated SQL may read the current portfolio view only.
"""

# Named-borrower lookup is the narrow PII use case needed by the Workbench. More sensitive
# fields stay absent from the model context even for privileged roles.
NAME_PII_COLUMN_IDS = frozenset({
    "loan.customer_name", "loan.agent_name", "disb.customer_name",
    "repay.customer_name", "risk.customer_name", "customer.full_name",
    "customer.dob", "customer.mobile", "customer.email", "customer.pan",
    "customer.aadhaar", "customer.city", "customer.district", "customer.pincode",
    "customer.agency_name", "kyc.customer_name", "kyc.number", "kyc.expiry",
    "agent.name", "agent.mobile", "agent.email", "msme.customer_name",
    "msme.firm_name", "msme.mobile",
})


def _system_prompt(allow_pii: bool) -> str:
    pii_rule = (
        "- You may use listed PII columns only when the user's question explicitly needs "
        "that borrower, customer, agent, KYC or MSME detail. Read-only person-level lists, "
        "rankings and exports are allowed during the open-access rollout; never broaden a "
        "person-level query beyond the fields the user explicitly requested."
        if allow_pii
        else "- Never reference customer names, dates of birth, addresses, PIN codes, "
             "PAN, Aadhaar or income."
    )
    return SYSTEM_PROMPT.format(pii_rule=pii_rule)


@dataclass(slots=True)
class SqlAttempt:
    sql: str = ""
    tables: list[str] = field(default_factory=list)
    explanation: str = ""
    validated: bool = False
    attempts: int = 0
    duration_ms: int = 0
    model: str = ""
    provider: str = ""
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    pii_columns: list[str] = field(default_factory=list)
    column_units: dict[str, str] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)


async def generate(
    question: str,
    *,
    catalog: Catalog | None = None,
    allow_pii: bool = False,
    preferred_tables: list[str] | None = None,
    client=None,
) -> SqlAttempt:
    """Generate and validate SQL. Returns an attempt whose `validated` flag is the gate."""
    cat = catalog or get_catalog()
    llm = client or get_llm_client()

    hits = retrieve(question, catalog=cat, use_vectors=settings.nlq_catalog_vectors)
    selected_tables = [
        table for table in (preferred_tables or []) if table in cat.allowed_tables()
    ]
    context = _context_block(
        hits,
        cat,
        allow_pii=allow_pii,
        tables=selected_tables or None,
    )

    messages = [
        {
            "role": "system",
            "content": (
                catalog_block(cat)
                + "\n\nSQL GENERATION TASK INSTRUCTIONS\n"
                + _system_prompt(allow_pii)
                + "\n\nRETRIEVED TABLE DETAIL\n"
                + context
            ),
        },
        *_few_shots(),
        {"role": "user", "content": question},
    ]

    attempt = SqlAttempt()
    schema = sql_schema()

    for round_number in range(2):  # initial + one repair
        attempt.attempts += 1
        request_messages = deepcopy(messages)
        try:
            result = await llm.complete(
                messages=messages,
                json_schema=schema,
                call_purpose="sql_repair" if round_number else "sql_generate",
                call_kind="repair" if round_number else "planned",
                prompt_version=SQL_PROMPT_VERSION,
                catalog_version=cat.version,
                prefix_hash=stable_hash(
                    catalog_block(cat)
                    + "\n\nSQL GENERATION TASK INSTRUCTIONS\n"
                    + _system_prompt(allow_pii)
                ),
                max_output_tokens=900,
            )
        except LLMError as exc:
            attempt.error = str(exc)
            attempt.trace.append({
                "round": round_number + 1,
                "request_messages": request_messages,
                "error": str(exc),
            })
            return attempt

        attempt.duration_ms += result.duration_ms
        attempt.model, attempt.provider = result.model, result.provider
        trace_item: dict[str, Any] = {
            "round": round_number + 1,
            "call_purpose": "sql_repair" if round_number else "sql_generate",
            "request_messages": request_messages,
            "assistant_message": deepcopy(result.assistant_message) if result.assistant_message else {
                "role": "assistant", "content": result.text,
            },
            "model": result.model,
            "provider": result.provider,
        }
        attempt.trace.append(trace_item)

        try:
            payload = result.json()
        except LLMError as exc:
            attempt.error = str(exc)
            trace_item["validation"] = {"status": "protocol_error", "error": str(exc)}
            continue

        candidate = str(payload.get("sql", "")).strip()
        attempt.sql = candidate
        attempt.explanation = str(payload.get("explanation", ""))[:300]

        try:
            checked = validate(
                candidate,
                catalog=cat,
                allow_pii=allow_pii,
                allowed_pii_columns={
                    cat.columns[column_id].column for column_id in NAME_PII_COLUMN_IDS
                    if column_id in cat.columns
                } if allow_pii else None,
            )
            from app.core.logging import log_parsed_output

            log_parsed_output(
                f"NLQ text-to-SQL validated on round {round_number + 1}",
                event="text_to_sql",
                sql=candidate,
                explanation=attempt.explanation,
                duration_ms=getattr(result, "duration_ms", 0.0),
                status="validated",
                round=round_number + 1,
            )
        except ValidationError as exc:
            attempt.error = str(exc)
            trace_item["candidate_sql"] = candidate
            trace_item["validation"] = {"status": "rejected", "error": str(exc)}
            logger.info("NLQ text-to-SQL rejected on round %d: %s", round_number + 1, exc)
            from app.core.logging import log_parsed_output

            log_parsed_output(
                f"NLQ text-to-SQL rejected on round {round_number + 1}: {exc}",
                event="text_to_sql",
                sql=candidate,
                status="validation_error",
                error=str(exc),
                duration_ms=getattr(result, "duration_ms", 0.0),
                round=round_number + 1,
            )
            # The model sees the specific reason. An open-ended "try again" reproduces the
            # same mistake.
            messages = [
                *messages,
                {"role": "assistant", "content": candidate},
                {
                    "role": "user",
                    "content": (
                        f"That statement was rejected: {exc}\n"
                        "Rewrite it to satisfy every hard rule, or return an empty sql "
                        "string if the question cannot be answered from these tables."
                    ),
                },
            ]
            continue

        attempt.sql = checked.sql
        attempt.tables = checked.tables
        attempt.pii_columns = checked.pii_columns
        attempt.column_units = _infer_column_units(checked.sql, checked.tables, cat)
        attempt.validated = True
        trace_item["candidate_sql"] = candidate
        trace_item["validated_sql"] = checked.sql
        trace_item["validation"] = {"status": "accepted", "tables": checked.tables}
        attempt.error = ""
        if checked.limit_injected:
            attempt.warnings.append("A row limit was applied to bound the result.")
        attempt.warnings.append(
            "Generated automatically and not covered by a reviewed metric definition — "
            "check the SQL before relying on this figure."
        )
        return attempt

    return attempt


def _infer_column_units(sql: str, tables: list[str], catalog: Catalog) -> dict[str, str]:
    """Carry catalog units through generated aliases such as `total_security_value`.

    A generated SUM would otherwise render as a plain count even when its source column is
    INR. The validator has already proved every referenced column is real at this point.
    """
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


def _context_block(
    hits,
    catalog: Catalog,
    *,
    allow_pii: bool = False,
    tables: list[str] | None = None,
) -> str:
    """Real DDL for the retrieved tables, plus the declared join paths between them.

    Without the join block the model sees two tables and no stated way to relate them,
    which is precisely when it invents a join condition.
    """
    lines: list[str] = ["TABLES YOU MAY USE"]
    selected_tables = tables or hits.tables
    for table_name in selected_tables:
        entry = catalog.table_by_name(table_name)
        if entry is None:
            continue
        lines.append(f"\n{table_name}  -- {entry.label}: {entry.grain}")
        if entry.notes:
            lines.append(f"  -- NOTE: {' '.join(entry.notes.split())[:300]}")
        for column in catalog.columns_for(table_name):
            if column.is_pii and not (allow_pii and column.id in NAME_PII_COLUMN_IDS):
                continue
            lines.append(f"  {column.column:32} -- {column.label} ({column.unit})")

    selected_joins = [
        join
        for join in catalog.joins
        if join.left in selected_tables and join.right in selected_tables
    ]
    if selected_joins:
        lines.append("\nJOIN PATHS (use exactly these conditions)")
        for join in selected_joins:
            conditions = " AND ".join(f"{join.left}.{a} = {join.right}.{b}" for a, b in join.on)
            lines.append(f"  {conditions}")

    if hits.enum_values:
        lines.append("\nCODE VALUES")
        for value in hits.enum_values:
            lines.append(f"  {value['dimension']} {value['code']} = {value['label']}")

    return "\n".join(lines)


def _few_shots() -> list[dict[str, str]]:
    return [
        {
            "role": "user",
            "content": "What is the average interest rate on gold loans by branch?",
        },
        {
            "role": "assistant",
            "content": (
                '{"sql":"SELECT application_branch_code, AVG(interest_rate) AS avg_rate '
                "FROM gold.semantic_loan_account WHERE product_code = 1 "
                'AND sanction_date >= DATE \'2023-01-01\' '
                'GROUP BY application_branch_code LIMIT 100",'
                '"tables":["gold.semantic_loan_account"],'
                '"explanation":"Average rate per branch for product 1."}'
            ),
        },
        {
            "role": "user",
            "content": "Which accounts have missed the most instalments?",
        },
        {
            "role": "assistant",
            "content": (
                '{"sql":"SELECT loan_account_number, dpd_days, total_overdue '
                "FROM gold.semantic_portfolio_snapshot "
                'WHERE dpd_days > 0 ORDER BY dpd_days DESC, total_overdue DESC '
                'LIMIT 100",'
                '"tables":["gold.semantic_portfolio_snapshot"],'
                '"explanation":"Current delinquent accounts, worst first."}'
            ),
        },
    ]


def lineage_for(attempt: SqlAttempt, row_count: int, duration_ms: int) -> Lineage:
    """Lineage for generated, validated SQL."""
    return Lineage(
        path="text_to_sql",
        sql=attempt.sql,
        display_sql=attempt.sql,
        parameters={},
        source_tables=attempt.tables,
        formulas={},
        row_count=row_count,
        duration_ms=duration_ms,
        warnings=list(attempt.warnings),
        unverified=True,
    )
