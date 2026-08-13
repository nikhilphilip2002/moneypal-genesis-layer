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
import re
from dataclasses import dataclass, field
from typing import Any

from sqlglot import exp

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.contracts import Lineage
from app.services.nlq.llm import LLMError, get_llm_client
from app.services.nlq.llm.schemas import sql_schema
from app.services.nlq.validator import ValidationError, validate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You write a single PostgreSQL SELECT statement answering the user's question about a \
lending book. You output JSON only.

HARD RULES — a statement breaking any of these is discarded:
- Exactly one SELECT statement. No semicolons, no DDL, no DML, no CTE that writes.
- Schema-qualify every table as silver.<table>. Never reference bronze, public, \
pg_catalog or information_schema.
- Never use SELECT * or table.*. Name every column.
- Every join must have an explicit ON condition.
- Always include a LIMIT of at most 5000.
- Always bound the query with a date filter when the table has a date column.
- Never reference a column that is not listed in the schema below.
{pii_rule}

DOMAIN
- Indian financial year runs 1 April to 31 March.
- Account keys are compound: every join must include entity_num as well as the account \
number, or rows from two entities will be merged.
- asset_classification_details is an EVENT LOG, not a snapshot. For an as-of figure use \
DISTINCT ON (entity, account) ... ORDER BY ... effective_date DESC with \
effective_date <= the date. Never filter it with effective_date = a date.
"""

# Named-borrower lookup is the narrow PII use case needed by the Workbench. More sensitive
# fields stay absent from the model context even for privileged roles.
NAME_PII_COLUMN_IDS = frozenset({
    "loan.customer_name",
    "customer.first_name",
    "customer.last_name",
})


def _system_prompt(allow_pii: bool) -> str:
    pii_rule = (
        "- You may use listed borrower-name columns only when needed to identify the "
        "borrower in the user's question. Do not return names unless the question asks "
        "for them. Never reference dates of birth, addresses, PIN codes, PAN, Aadhaar or "
        "income."
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


async def generate(
    question: str,
    *,
    catalog: Catalog | None = None,
    allow_pii: bool = False,
    client=None,
) -> SqlAttempt:
    """Generate and validate SQL. Returns an attempt whose `validated` flag is the gate."""
    cat = catalog or get_catalog()
    llm = client or get_llm_client()

    exact = _named_borrower_principal_attempt(question, cat, allow_pii=allow_pii)
    if exact is not None:
        logger.info("NLQ selected deterministic named-borrower principal lookup")
        return exact

    hits = retrieve(question, catalog=cat)
    context = _context_block(hits, cat, allow_pii=allow_pii)

    messages = [
        {"role": "system", "content": _system_prompt(allow_pii)},
        {"role": "system", "content": context},
        *_few_shots(),
        {"role": "user", "content": question},
    ]

    attempt = SqlAttempt()
    schema = sql_schema()

    for round_number in range(2):  # initial + one repair
        attempt.attempts += 1
        try:
            result = await llm.complete(
                messages=messages, json_schema=schema, max_tokens=800, temperature=0.0
            )
        except LLMError as exc:
            attempt.error = str(exc)
            return attempt

        attempt.duration_ms += result.duration_ms
        attempt.model, attempt.provider = result.model, result.provider

        try:
            payload = result.json()
        except LLMError as exc:
            attempt.error = str(exc)
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
        except ValidationError as exc:
            attempt.error = str(exc)
            logger.info("NLQ text-to-SQL rejected on round %d: %s", round_number + 1, exc)
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
        attempt.validated = True
        attempt.error = ""
        if checked.limit_injected:
            attempt.warnings.append("A row limit was applied to bound the result.")
        attempt.warnings.append(
            "Generated automatically and not covered by a reviewed metric definition — "
            "check the SQL before relying on this figure."
        )
        return attempt

    return attempt


_NAMED_PRINCIPAL_RE = re.compile(
    r"\b(?:principal|principle)\b.*\b(?:paid|repaid|collected|recovered)\b\s+"
    r"(?:by|for)\s+(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.IGNORECASE,
)


def named_borrower_principal_name(question: str) -> str | None:
    """Return the explicit borrower name for the supported cumulative-principal intent."""
    if re.search(
        r"\b(?:today|yesterday|month|quarter|year|fy\d*|between|from|since|before|after)\b",
        question,
        re.IGNORECASE,
    ):
        return None
    match = _NAMED_PRINCIPAL_RE.search(question.strip())
    if match is None:
        return None
    return match.group("name").strip(" .?!") or None


def _named_borrower_principal_attempt(
    question: str,
    catalog: Catalog,
    *,
    allow_pii: bool,
) -> SqlAttempt | None:
    """Deterministic current cumulative principal for one explicitly named borrower.

    This common lookup should not depend on an LLM reproducing opaque Prosper column
    names. More complex questions (especially those naming a period) continue through the
    generated-SQL path.
    """
    if not allow_pii:
        return None
    borrower = named_borrower_principal_name(question)
    if not borrower:
        return None

    # sqlglot owns literal quoting, including apostrophes; user text is never interpolated
    # as SQL syntax.
    literal = exp.Literal.string(borrower).sql(dialect="postgres")
    sql = (
        "SELECT SUM(gnlnac_pri_repay_amt) AS principal_repaid "
        "FROM silver.loan_account_master "
        f"WHERE LOWER(TRIM(gnlnac_cust_name)) = LOWER({literal}) "
        "AND gnlnac_sanc_date <= CURRENT_DATE LIMIT 5000"
    )
    checked = validate(
        sql,
        catalog=catalog,
        allow_pii=True,
        allowed_pii_columns={"gnlnac_cust_name"},
    )
    return SqlAttempt(
        sql=checked.sql,
        tables=checked.tables,
        explanation="Cumulative principal repaid across the borrower's loan accounts.",
        validated=True,
        attempts=0,
        model="deterministic",
        provider="catalog",
        warnings=[
            "Borrower matched by exact normalized name.",
            "The amount is cumulative as of the latest loan-account data load.",
        ],
        pii_columns=checked.pii_columns,
    )


def _context_block(hits, catalog: Catalog, *, allow_pii: bool = False) -> str:
    """Real DDL for the retrieved tables, plus the declared join paths between them.

    Without the join block the model sees two tables and no stated way to relate them,
    which is precisely when it invents a join condition.
    """
    lines: list[str] = ["TABLES YOU MAY USE"]
    for table_name in hits.tables:
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

    if hits.joins:
        lines.append("\nJOIN PATHS (use exactly these conditions)")
        for join_id in hits.joins:
            join = next((j for j in catalog.joins if j.id == join_id), None)
            if join is None:
                continue
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
                '{"sql":"SELECT gnlnac_appl_brn_code, AVG(gnlnac_ln_intrate) AS avg_rate '
                "FROM silver.loan_account_master WHERE gnlnac_prod_code = 1 "
                'AND gnlnac_sanc_date >= DATE \'2023-01-01\' '
                'GROUP BY gnlnac_appl_brn_code LIMIT 100",'
                '"tables":["silver.loan_account_master"],'
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
                '{"sql":"SELECT DISTINCT ON (ascd_entity_num, ascd_account_num) '
                "ascd_account_num, ascd_no_inst_not_paid, ascd_dpd_days "
                "FROM silver.asset_classification_details "
                'WHERE ascd_effective_date <= CURRENT_DATE '
                'ORDER BY ascd_entity_num, ascd_account_num, ascd_effective_date DESC '
                'LIMIT 100",'
                '"tables":["silver.asset_classification_details"],'
                '"explanation":"Latest classification per account, worst first."}'
            ),
        },
    ]


def lineage_for(attempt: SqlAttempt, row_count: int, duration_ms: int) -> Lineage:
    """Lineage for the fallback path, marked unverified so the UI can flag it."""
    return Lineage(
        path="text_to_sql",
        sql=attempt.sql,
        source_tables=attempt.tables,
        formulas={},
        row_count=row_count,
        duration_ms=duration_ms,
        warnings=list(attempt.warnings),
        unverified=True,
    )
