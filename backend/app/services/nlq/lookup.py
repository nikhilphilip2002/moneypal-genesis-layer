"""Deterministic customer and account lookups for the Workbench.

These questions are record retrieval, not metrics.  The planner only extracts a small,
closed intent; this module owns the SQL and the displayed fields so a borrower name or
identifier can never turn into an open-ended generated query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from sqlglot import exp

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import ChartSpec, ClarifyPlan, LookupPlan
from app.services.nlq.executor import execute_raw
from app.services.nlq.pipeline import run_sql
from app.services.nlq.text_to_sql import SqlAttempt, _normalized_borrower_sql
from app.services.nlq.validator import validate


_REPAYMENT_CUE = re.compile(r"\b(?:repayment|payment)\s+histor(?:y|ies)\b", re.I)
_CUSTOMER_ID = re.compile(
    r"\b(?:customer|borrower|client)\s*(?:id|number|no\.?|#)\s*"
    r"(?:is|was|=|:|-)?\s*(?P<value>[0-9][0-9,]*(?:\.0+)?)\b",
    re.I,
)
_ACCOUNT_ID = re.compile(
    r"\b(?:loan\s+)?account\s*(?:number|no\.?|#)\s*"
    r"(?:is|was|=|:|-)?\s*(?P<value>[a-z0-9][a-z0-9,._/-]*)\b",
    re.I,
)
_NAME_AFTER_HISTORY = re.compile(
    r"\b(?:repayment|payment)\s+histor(?:y|ies)\s+(?:of|for)\s+"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_NAME_BEFORE_HISTORY = re.compile(
    r"^(?:what\s+is|show(?:\s+me)?|give\s+me)?\s*"
    r"(?P<name>[\w .'-]{2,100}?)\s*(?:'s\s+)?"
    r"(?:repayment|payment)\s+histor(?:y|ies)\s*[?!.]*$",
    re.I,
)
_GENDER_ACCOUNT_SAMPLE = re.compile(
    r"\b(?:male|men)\b.*\b(?:female|women)\b|"
    r"\b(?:female|women)\b.*\b(?:male|men)\b",
    re.I,
)
_LOAN_DETAIL_CUE = re.compile(
    r"\b(?:loan\s+amount|sanction(?:ed)?|disburs(?:ed|ement)|loan\s+date|date)\b",
    re.I,
)


@dataclass(slots=True)
class LookupResult:
    chart: ChartSpec | None = None
    clarification: ClarifyPlan | None = None
    no_match: bool = False


def _plain_identifier(value: str) -> str:
    text = str(value).strip().replace(",", "")
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def detect(question: str) -> LookupPlan | None:
    """Recognise selector + requested record family without matching whole questions."""
    text = " ".join(str(question or "").split())

    if (
        _GENDER_ACCOUNT_SAMPLE.search(text)
        and re.search(r"\baccount(?:\s+(?:number|no\.?))?s?\b", text, re.I)
    ):
        return LookupPlan(
            selector="gender", value="male,female", detail="account_sample",
            reasoning="one deterministic loan-account sample for each requested gender",
        )

    customer = _CUSTOMER_ID.search(text)
    account = _ACCOUNT_ID.search(text)
    if _REPAYMENT_CUE.search(text):
        if customer:
            selector, value = "customer_id", _plain_identifier(customer.group("value"))
        elif account:
            selector, value = "loan_account", _plain_identifier(account.group("value"))
        else:
            match = _NAME_AFTER_HISTORY.search(text) or _NAME_BEFORE_HISTORY.search(text)
            if not match:
                return None
            selector, value = "borrower_name", match.group("name").strip(" .?!")
        return LookupPlan(
            selector=selector, value=value, detail="repayment_history",
            reasoning="governed borrower repayment-event history",
        )

    if customer and _LOAN_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="customer_id", value=_plain_identifier(customer.group("value")),
            detail="loan_details",
            reasoning="governed loan-account origination and disbursement details",
        )
    if account and _LOAN_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="loan_account", value=_plain_identifier(account.group("value")),
            detail="loan_details",
            reasoning="governed loan-account origination and disbursement details",
        )
    return None


def _literal(value: str) -> str:
    return exp.Literal.string(value).sql(dialect="postgres")


def _validated_attempt(
    sql: str,
    *,
    catalog: Catalog,
    explanation: str,
    units: dict[str, str],
    pii_columns: set[str] | None = None,
) -> SqlAttempt:
    checked = validate(
        sql,
        catalog=catalog,
        allow_pii=bool(pii_columns),
        allowed_pii_columns=pii_columns,
    )
    return SqlAttempt(
        sql=checked.sql,
        tables=checked.tables,
        explanation=explanation,
        validated=True,
        attempts=0,
        model="deterministic",
        provider="catalog",
        pii_columns=checked.pii_columns,
        column_units=units,
        reviewed=True,
    )


def _candidate_customers(name: str, catalog: Catalog) -> list[dict]:
    literal, stored_name, display_name = _normalized_borrower_sql(name)
    sql = (
        f"SELECT {display_name} AS borrower_name, customer_id::text AS customer_id, "
        "MIN(loan_account_number::text) AS account_number "
        "FROM gold.loan_account_master "
        f"WHERE {stored_name} LIKE {literal} || '%' AND sanction_date <= CURRENT_DATE "
        f"GROUP BY {display_name}, customer_id ORDER BY {display_name}, customer_id LIMIT 20"
    )
    attempt = _validated_attempt(
        sql, catalog=catalog, explanation="Borrower candidates from the governed loan master.",
        units={"borrower_name": "text", "customer_id": "text", "account_number": "text"},
        pii_columns={"customer_name"},
    )
    return execute_raw(attempt.sql).rows


def _where(plan: LookupPlan) -> str:
    value = _literal(_plain_identifier(plan.value).lower())
    if plan.selector == "loan_account":
        return f"LOWER(loan_account_number::text) = {value}"
    return (
        "LOWER(REGEXP_REPLACE(customer_id::text, '\\.0+$', '')) = " + value
    )


def _loan_details(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT customer_id::text AS customer_id, "
        "loan_account_number::text AS loan_account_number, sanction_amount, sanction_date, "
        "disbursed_amount, first_disbursement_date "
        "FROM gold.loan_account_master WHERE " + _where(plan) +
        " AND sanction_date <= CURRENT_DATE ORDER BY sanction_date DESC, "
        "loan_account_number LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation=(
            "Sanction and cumulative disbursement details for each matched loan account."
        ),
        units={
            "customer_id": "text", "loan_account_number": "text",
            "sanction_amount": "inr", "sanction_date": "date",
            "disbursed_amount": "inr", "first_disbursement_date": "date",
        },
    )


def _repayment_history(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT loan_account_number::text AS loan_account_number, repayment_date, "
        "principal_due, interest_due, total_due, principal_paid, interest_paid, total_paid, "
        "collection_shortfall, collection_efficiency, "
        "SUM(total_due) OVER () AS history_total_due, "
        "SUM(total_paid) OVER () AS history_total_paid, "
        "SUM(collection_shortfall) OVER () AS history_total_shortfall "
        "FROM gold.loan_repayment_events WHERE " + _where(plan) +
        " AND repayment_date <= CURRENT_DATE ORDER BY repayment_date DESC, "
        "repayment_sequence DESC LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Repayment events newest first, with totals across all matched events.",
        units={
            "loan_account_number": "text", "repayment_date": "date",
            "principal_due": "inr", "interest_due": "inr", "total_due": "inr",
            "principal_paid": "inr", "interest_paid": "inr", "total_paid": "inr",
            "collection_shortfall": "inr", "collection_efficiency": "percent",
            "history_total_due": "inr", "history_total_paid": "inr",
            "history_total_shortfall": "inr",
        },
    )


def _gender_sample(catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT gender, loan_account_number FROM ("
        "SELECT CASE WHEN LOWER(TRIM(customer.gender)) IN ('m', 'male') THEN 'Male' "
        "ELSE 'Female' END AS gender, loan.loan_account_number::text AS loan_account_number, "
        "ROW_NUMBER() OVER (PARTITION BY CASE WHEN LOWER(TRIM(customer.gender)) "
        "IN ('m', 'male') THEN 'Male' ELSE 'Female' END "
        "ORDER BY loan.loan_account_number) AS sample_rank "
        "FROM gold.customer_master AS customer JOIN gold.loan_account_master AS loan "
        "ON customer.entity_num = loan.entity_num AND customer.customer_id = loan.customer_id "
        "WHERE LOWER(TRIM(customer.gender)) IN ('m', 'male', 'f', 'female') "
        "AND loan.sanction_date <= CURRENT_DATE) AS ranked "
        "WHERE sample_rank = 1 ORDER BY gender LIMIT 2"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="One stable loan-account sample for each recorded male/female gender.",
        units={"gender": "text", "loan_account_number": "text"},
    )


def run(plan: LookupPlan, *, role: str | None, catalog: Catalog | None = None) -> LookupResult:
    cat = catalog or get_catalog()
    effective = plan
    if plan.selector == "borrower_name":
        candidates = _candidate_customers(plan.value, cat)
        if not candidates:
            return LookupResult(no_match=True)
        identities = {str(row.get("customer_id", "")): row for row in candidates}
        if len(identities) != 1:
            suggestions = []
            for customer_id, row in list(identities.items())[:3]:
                name = str(row.get("borrower_name", ""))
                account = _plain_identifier(str(row.get("account_number", "")))
                suffix = account[-4:] if account else "unknown"
                prefix = "Show repayment history for" if plan.detail == "repayment_history" else "Show loans for"
                suggestions.append(
                    f"{prefix} customer ID {customer_id} ({name}, account ending {suffix})"
                )
            return LookupResult(clarification=ClarifyPlan(
                question="Several borrowers match that name. Choose the intended customer:",
                suggestions=suggestions,
            ))
        customer_id = next(iter(identities))
        effective = plan.model_copy(update={"selector": "customer_id", "value": customer_id})

    if effective.detail == "loan_details":
        attempt = _loan_details(effective, cat)
    elif effective.detail == "repayment_history":
        attempt = _repayment_history(effective, cat)
    else:
        attempt = _gender_sample(cat)

    chart = run_sql(attempt, question=plan.reasoning, role=role, catalog=cat)
    if not chart.rows:
        return LookupResult(no_match=True)
    chart.subtitle = "Governed read-only record lookup"
    if effective.detail == "repayment_history":
        first = chart.rows[0]
        totals = {
            "history_total_due": first.get("history_total_due"),
            "history_total_paid": first.get("history_total_paid"),
            "history_total_shortfall": first.get("history_total_shortfall"),
        }
        for row in chart.rows:
            for field in totals:
                row.pop(field, None)
        chart.columns = [column for column in chart.columns if column.name not in totals]
        chart.series = [series for series in chart.series if series.field not in totals]
        from app.services.nlq.narrator import format_value
        chart.summary = (
            f"{chart.lineage.row_count:,} repayment event(s) returned. Total due was "
            f"{format_value(totals['history_total_due'], 'inr')}; total paid was "
            f"{format_value(totals['history_total_paid'], 'inr')}; total shortfall was "
            f"{format_value(totals['history_total_shortfall'], 'inr')}."
        )
    return LookupResult(chart=chart)


__all__ = ["LookupResult", "detect", "run"]
