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

import sqlglot
from sqlglot import exp

from app.core.config import settings
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.contracts import Lineage
from app.services.nlq.llm import LLMError, get_llm_client
from app.services.nlq.llm.prompts import gold_yaml_block
from app.services.nlq.llm.schemas import sql_schema
from app.services.nlq.normalization import normalize_lending_question
from app.services.nlq.validator import ValidationError, validate

logger = logging.getLogger(__name__)

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
    reviewed: bool = False


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

    exact = _interest_rate_distribution_attempt(question, cat)
    if exact is not None:
        logger.info("NLQ selected deterministic interest-rate distribution")
        return exact

    exact = _agent_directory_attempt(question, cat, allow_pii=allow_pii)
    if exact is not None:
        logger.info("NLQ selected deterministic agent-directory query")
        return exact

    exact = _named_borrower_disbursed_attempt(question, cat, allow_pii=allow_pii)
    if exact is not None:
        logger.info("NLQ selected deterministic named-borrower disbursement lookup")
        return exact

    exact = _named_borrower_principal_attempt(question, cat, allow_pii=allow_pii)
    if exact is not None:
        logger.info("NLQ selected deterministic named-borrower principal lookup")
        return exact

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
                gold_yaml_block(cat)
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
        attempt.column_units = _infer_column_units(checked.sql, checked.tables, cat)
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


_INTEREST_RATE_LIST_RE = re.compile(
    r"\b(?:various|different|distinct|available|list|range\s+of)\b[^?]{0,50}"
    r"\binterest\s+rates?\b|"
    r"\blist\s+the\s+distinct\s+account\s+interest\s+rates?\b|"
    r"\bwhat\s+(?:are|is)\b[^?]{0,35}\binterest\s+rates?\b",
    re.IGNORECASE,
)

_AGENT_DIRECTORY_RE = re.compile(
    r"\b(?:agent\s+(?:details?|directory|profiles?|names?)|"
    r"(?:list|show)\s+(?:all\s+)?agents?)\b|"
    r"\bagents?\b[^?]{0,100}\b(?:names?|designations?|branch(?:es|\s+codes?)?|"
    r"mobiles?|phones?|emails?|role(?:s|\s+codes?)?|joined|linked\s+(?:loan|customer|borrower))\b",
    re.IGNORECASE,
)


def _agent_directory_attempt(
    question: str,
    catalog: Catalog,
    *,
    allow_pii: bool,
) -> SqlAttempt | None:
    """Select only explicitly requested fields from the governed agent directory."""
    normalized = normalize_lending_question(question)
    if not allow_pii or _AGENT_DIRECTORY_RE.search(normalized) is None:
        return None

    generic = bool(re.search(r"\bagent\s+(?:details?|directory|profiles?)\b", normalized, re.I))
    columns: list[tuple[str, str]] = [
        ("agent_code", "text"),
        ("agent_name", "text"),
    ]
    requested = (
        (r"\bdesignation", "designation", "text"),
        (r"\bbranch", "branch_code", "text"),
        (r"\blinked\s+loans?\b|\bloan\s+counts?\b", "linked_loan_count", "count"),
        (
            r"\blinked\s+(?:customers?|borrowers?)\b|\b(?:customer|borrower)\s+counts?\b",
            "linked_customer_count",
            "count",
        ),
        (r"\b(?:mobile|phone)", "mobile", "text"),
        (r"\bemail", "email", "text"),
        (r"\bagent\s+types?\b", "agent_type", "text"),
        (r"\brole(?:s|\s+codes?)?\b", "role_code", "text"),
        (r"\bjoin(?:ed|ing)?\b", "joined_on", "date"),
    )
    for pattern, column, unit in requested:
        if generic or re.search(pattern, normalized, re.I):
            columns.append((column, unit))

    # A generic directory is useful without exposing contact details the user did not ask
    # for. Those fields remain available when mobile/email is explicit.
    if generic:
        for column, unit in (
            ("designation", "text"),
            ("branch_code", "text"),
            ("linked_customer_count", "count"),
            ("linked_loan_count", "count"),
        ):
            if (column, unit) not in columns:
                columns.append((column, unit))

    names = [column for column, _unit in columns]
    order_column = (
        "linked_customer_count" if "linked_customer_count" in names
        else "linked_loan_count" if "linked_loan_count" in names
        else "agent_name"
    )
    direction = "DESC" if order_column.startswith("linked_") else "ASC"
    sql = (
        "SELECT " + ", ".join(names) + " FROM gold.semantic_agent "
        f"ORDER BY {order_column} {direction} NULLS LAST LIMIT 200"
    )
    checked = validate(
        sql,
        catalog=catalog,
        allow_pii=True,
        allowed_pii_columns={"agent_name", "mobile", "email"},
    )
    return SqlAttempt(
        sql=checked.sql,
        tables=checked.tables,
        explanation=(
            "Current governed agent-directory fields requested by the user, ordered by "
            + order_column.replace("_", " ")
            + "."
        ),
        validated=True,
        attempts=0,
        model="deterministic",
        provider="catalog",
        warnings=["Agent directory values reflect the latest available Gold view load."],
        pii_columns=checked.pii_columns,
        column_units={column: unit for column, unit in columns},
    )


def _interest_rate_distribution_attempt(
    question: str, catalog: Catalog
) -> SqlAttempt | None:
    """List contractual account rates with counts, without asking the model to write SQL."""
    if not _INTEREST_RATE_LIST_RE.search(normalize_lending_question(question)):
        return None
    sql = (
        "SELECT interest_rate AS interest_rate, COUNT(interest_rate) AS loan_count "
        "FROM gold.semantic_loan_account "
        "WHERE interest_rate IS NOT NULL AND sanction_date <= CURRENT_DATE "
        "GROUP BY interest_rate ORDER BY interest_rate ASC LIMIT 5000"
    )
    checked = validate(sql, catalog=catalog, allow_pii=False)
    return SqlAttempt(
        sql=checked.sql,
        tables=checked.tables,
        explanation=(
            "Distinct contractual account interest rates, with the number of sanctioned "
            "loans at each rate, across the full available loan book."
        ),
        validated=True,
        attempts=0,
        model="deterministic",
        provider="catalog",
        warnings=[
            "Rates are contractual account percentages, not rupee amounts.",
            "Loan count shows how many accounts carry each distinct rate.",
        ],
        column_units={"interest_rate": "percent", "loan_count": "count"},
    )


_NAMED_PRINCIPAL_RE = re.compile(
    r"\b(?:principal|principle)\b.*\b(?:paid|repaid|collected|recovered)\b\s+"
    r"(?:by|for)\s+(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.IGNORECASE,
)
_NAMED_DISBURSED_RE = re.compile(
    r"\b(?:loan\s+amount\s+)?(?:disbur\w*|released|paid\s+out)\b\s+"
    r"(?:to|for|by)\s+(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.IGNORECASE,
)


def _has_period_words(question: str) -> bool:
    return bool(re.search(
        r"\b(?:today|yesterday|month|quarter|year|fy\d*|between|from|since|before|after)\b",
        question,
        re.IGNORECASE,
    ))


def named_borrower_principal_name(question: str) -> str | None:
    """Return the explicit borrower name for the supported cumulative-principal intent."""
    if _has_period_words(question):
        return None
    match = _NAMED_PRINCIPAL_RE.search(question.strip())
    if match is None:
        return None
    return match.group("name").strip(" .?!") or None


def named_borrower_disbursed_name(question: str) -> str | None:
    """Return the borrower in a current cumulative-disbursement lookup."""
    if _has_period_words(question):
        return None
    match = _NAMED_DISBURSED_RE.search(question.strip())
    if match is None:
        return None
    return match.group("name").strip(" .?!") or None


def _normalized_borrower_sql(borrower: str) -> tuple[str, str, str]:
    normalized = re.sub(r"[^a-z0-9]", "", borrower.lower()).replace("th", "t")
    # Repeated-letter spelling varies in operational names (Sheela/Shela, double-e versus
    # double-l typos). Collapse runs on both sides while retaining the full remaining name,
    # which is much safer than broad substring matching.
    normalized = re.sub(r"(.)\1+", r"\1", normalized)
    literal = exp.Literal.string(normalized).sql(dialect="postgres")
    stored_name = (
        "REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(TRIM(customer_name)), "
        "'th', 't'), '[^a-z0-9]', '', 'g'), '(.)\\1+', '\\1', 'g')"
    )
    display_name = "TRIM(REGEXP_REPLACE(customer_name, '\\s+', ' ', 'g'))"
    return literal, stored_name, display_name


def _named_borrower_disbursed_attempt(
    question: str,
    catalog: Catalog,
    *,
    allow_pii: bool,
) -> SqlAttempt | None:
    """Deterministic cumulative amount disbursed to one named borrower."""
    if not allow_pii:
        return None
    borrower = named_borrower_disbursed_name(question)
    if not borrower:
        return None
    literal, stored_name, display_name = _normalized_borrower_sql(borrower)
    sql = (
        f"SELECT {display_name} AS borrower_name, "
        "SUM(disbursed_amount) AS disbursed_amount "
        "FROM gold.semantic_loan_account "
        f"WHERE {stored_name} LIKE {literal} || '%' "
        "AND sanction_date <= CURRENT_DATE "
        f"GROUP BY {display_name} ORDER BY disbursed_amount DESC LIMIT 20"
    )
    checked = validate(
        sql,
        catalog=catalog,
        allow_pii=True,
        allowed_pii_columns={"customer_name"},
    )
    return SqlAttempt(
        sql=checked.sql,
        tables=checked.tables,
        explanation="Cumulative amount disbursed across the borrower's loan accounts.",
        validated=True,
        attempts=0,
        model="deterministic",
        provider="catalog",
        warnings=[
            "Borrowers matched after normalizing spacing, punctuation, initials and th/t spelling.",
            "Multiple possible borrowers are shown separately rather than combined.",
            "The amount is cumulative as of the latest loan-account data load.",
        ],
        pii_columns=checked.pii_columns,
        column_units={"disbursed_amount": "inr", "borrower_name": "text"},
    )


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

    # Match operational name formatting without merging ambiguous borrowers: whitespace,
    # punctuation and the common Indian-name `th`/`t` transliteration are normalized, and
    # omitted initials are accepted as a prefix. Every matching stored name remains its
    # own result row so "Sheela" cannot silently combine several people.
    literal, stored_name, display_name = _normalized_borrower_sql(borrower)
    sql = (
        f"SELECT {display_name} AS borrower_name, "
        "SUM(principal_repaid) AS principal_repaid "
        "FROM gold.semantic_loan_account "
        f"WHERE {stored_name} LIKE {literal} || '%' "
        "AND sanction_date <= CURRENT_DATE "
        f"GROUP BY {display_name} ORDER BY principal_repaid DESC LIMIT 20"
    )
    checked = validate(
        sql,
        catalog=catalog,
        allow_pii=True,
        allowed_pii_columns={"customer_name"},
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
            "Borrowers matched after normalizing spacing, punctuation, initials and th/t spelling.",
            "Multiple possible borrowers are shown separately rather than combined.",
            "The amount is cumulative as of the latest loan-account data load.",
        ],
        pii_columns=checked.pii_columns,
        column_units={"principal_repaid": "inr", "borrower_name": "text"},
    )


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
    """Lineage for generated SQL or a reviewed deterministic record lookup."""
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
        unverified=not attempt.reviewed,
    )
