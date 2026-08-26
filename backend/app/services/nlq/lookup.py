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
    r"\b(?:loan\s+amount|sanction(?:ed)?|disburs(?:ed|e?ment)|loan\s+date|date)\b",
    re.I,
)
_CUSTOMER_DETAIL_CUE = re.compile(
    r"\b(?:details?|profiles?|information|info|infor\w*)\b|"
    r"\b(?:show|give|get|find)\s+(?:me\s+)?(?:the\s+)?(?:customer|borrower|client)\b",
    re.I,
)
_NAMED_LOAN_DETAIL = re.compile(
    r"\b(?:customer|borrower|client)\s+(?!id\b|number\b|no\.?\b|#)"
    r"(?P<name>[\w .'-]{2,100})\s*[?!.]*$",
    re.I,
)
_BRANCH_DIRECTORY_CUE = re.compile(
    r"\b(?:what|which)\s+(?:are|is)\s+(?:the\s+)?branches\b|"
    r"\bbranches?\s+(?:are|is)\s+there\b|"
    r"\b(?:list|show)\s+(?:me\s+)?(?:all\s+)?branches\b|"
    r"\bavailable\s+branches\b",
    re.I,
)
_AGENT_CODE = re.compile(r"\b(?P<value>(?:agnt|agent)[-_ ]?\d+)\b", re.I)
_AGENT_DETAIL_CUE = re.compile(
    r"\b(?:details?|profiles?|names?|information|info|infor\w*|show|get|give|about)\b",
    re.I,
)
_AGENT_COUNT_CUE = re.compile(
    r"\b(?:(?:how\s+many|number\s+of|count\s+of|total)\s+(?:active\s+)?agents?|"
    r"agents?\s+count)\b",
    re.I,
)


@dataclass(slots=True)
class LookupResult:
    chart: ChartSpec | None = None
    clarification: ClarifyPlan | None = None
    no_match: bool = False


def completions(term: str, kind: str = "all", catalog: Catalog | None = None) -> list[dict]:
    """Return bounded Gold-directory completions for the chat composer."""
    cat = catalog or get_catalog()
    text = " ".join(str(term or "").split()).strip()
    if len(text) < 2 or kind not in {"all", "borrower", "customer", "account", "agent"}:
        return []

    results: list[dict] = []
    if kind in {"all", "borrower", "customer", "account"}:
        normalized = re.sub(r"[^a-z0-9]", "", text.lower()).replace("th", "t")
        normalized = re.sub(r"(.)\1+", r"\1", normalized)
        name_literal = _literal(normalized)
        id_literal = _literal(_plain_identifier(text).lower())
        stored_name = (
            "REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(TRIM(customer_name)), "
            "'th', 't'), '[^a-z0-9]', '', 'g'), '(.)\\1+', '\\1', 'g')"
        )
        sql = (
            "SELECT TRIM(REGEXP_REPLACE(customer_name, '\\s+', ' ', 'g')) AS borrower_name, "
            "customer_id::text AS customer_id, MIN(loan_account_number::text) AS account_number "
            "FROM gold.loan_account_master WHERE sanction_date <= CURRENT_DATE AND ("
            f"{stored_name} LIKE {name_literal} || '%' OR "
            f"LOWER(customer_id::text) LIKE {id_literal} || '%' OR "
            f"LOWER(loan_account_number::text) LIKE {id_literal} || '%') "
            "GROUP BY TRIM(REGEXP_REPLACE(customer_name, '\\s+', ' ', 'g')), customer_id "
            "ORDER BY borrower_name, customer_id LIMIT 8"
        )
        attempt = _validated_attempt(
            sql, catalog=cat, explanation="Chat entity completions from governed borrowers.",
            units={"borrower_name": "text", "customer_id": "text", "account_number": "text"},
            pii_columns={"customer_name"},
        )
        for row in execute_raw(attempt.sql).rows:
            customer_id = _plain_identifier(str(row.get("customer_id", "")))
            account = _plain_identifier(str(row.get("account_number", "")))
            name = str(row.get("borrower_name", "")).strip()
            if kind == "customer":
                value, result_kind = customer_id, "customer"
            elif kind == "account":
                value, result_kind = account, "account"
            else:
                value, result_kind = name, "borrower"
            results.append({
                "kind": result_kind,
                "value": value,
                "label": name or f"Customer {customer_id}",
                "detail": f"Customer {customer_id} · Account ending {account[-4:]}",
            })

    if kind in {"all", "agent"}:
        literal = _literal(text.lower())
        sql = (
            "SELECT agent_code, agent_name, designation FROM gold.agent_master "
            f"WHERE LOWER(agent_code) LIKE {literal} || '%' "
            f"OR LOWER(agent_name) LIKE '%' || {literal} || '%' "
            "ORDER BY agent_code LIMIT 8"
        )
        attempt = _validated_attempt(
            sql, catalog=cat, explanation="Chat entity completions from the governed agent directory.",
            units={"agent_code": "text", "agent_name": "text", "designation": "text"},
            pii_columns={"agent_name"},
        )
        for row in execute_raw(attempt.sql).rows:
            code = str(row.get("agent_code", "")).strip()
            name = str(row.get("agent_name", "")).strip()
            designation = str(row.get("designation", "") or "Agent").strip()
            results.append({
                "kind": "agent", "value": code, "label": name or code,
                "detail": f"{code} · {designation}",
            })
    return results[:8]


def _plain_identifier(value: str) -> str:
    text = str(value).strip().replace(",", "")
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def detect(question: str) -> LookupPlan | None:
    """Recognise selector + requested record family without matching whole questions."""
    text = " ".join(str(question or "").split())

    if _BRANCH_DIRECTORY_CUE.search(text):
        return LookupPlan(
            selector="branch", value="all", detail="branch_directory",
            reasoning="current governed branch directory",
        )

    if _AGENT_COUNT_CUE.search(text):
        return LookupPlan(
            selector="agent_code", value="all", detail="agent_count",
            reasoning="count of agents in the current governed agent directory",
        )

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
    agent = _AGENT_CODE.search(text)
    if agent and (
        _AGENT_DETAIL_CUE.search(text) or _AGENT_CODE.fullmatch(text.strip())
    ):
        return LookupPlan(
            selector="agent_code",
            value="AGNT" + re.sub(r"\D", "", agent.group("value")),
            detail="agent_details", reasoning="governed agent-directory details",
        )
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
    if customer and _CUSTOMER_DETAIL_CUE.search(text):
        return LookupPlan(
            selector="customer_id", value=_plain_identifier(customer.group("value")),
            detail="customer_summary",
            reasoning="governed customer and linked-loan summary",
        )
    if _LOAN_DETAIL_CUE.search(text):
        named = _NAMED_LOAN_DETAIL.search(text)
        if named:
            return LookupPlan(
                selector="borrower_name", value=named.group("name").strip(" .?!"),
                detail="loan_details",
                reasoning="governed borrower loan origination and disbursement details",
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


def _customer_summary(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    """Return the intentionally narrow customer profile requested by the UI."""
    value = _literal(_plain_identifier(plan.value).lower())
    sql = (
        "SELECT customer.customer_id::text AS customer_id, "
        "customer.full_name AS customer_name, "
        "loan.loan_account_number::text AS loan_account_number, "
        "loan.sanction_amount, loan.sanction_date, "
        "CONCAT_WS(', ', NULLIF(TRIM(customer.address_line1), ''), "
        "NULLIF(TRIM(customer.address_line2), ''), "
        "NULLIF(TRIM(customer.additional_address), '')) AS address, "
        "COALESCE(NULLIF(TRIM(customer.occupation_name), ''), "
        "NULLIF(TRIM(customer.occupation_type), ''), "
        "NULLIF(TRIM(customer.occupation_nature), '')) AS occupation, "
        "customer.home_branch_code, customer.agency_code, customer.agency_name "
        "FROM gold.customer_master AS customer "
        "LEFT JOIN gold.loan_account_master AS loan "
        "ON customer.entity_num = loan.entity_num "
        "AND customer.customer_id = loan.customer_id "
        "AND loan.sanction_date <= CURRENT_DATE "
        "WHERE LOWER(REGEXP_REPLACE(customer.customer_id::text, '\\.0+$', '')) = "
        + value +
        " ORDER BY loan.sanction_date DESC, loan.loan_account_number LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Requested customer profile fields and linked sanctioned loan accounts.",
        units={
            "customer_id": "text", "customer_name": "text",
            "loan_account_number": "text", "sanction_amount": "inr",
            "sanction_date": "date", "address": "text", "occupation": "text",
            "home_branch_code": "text", "agency_code": "text", "agency_name": "text",
        },
        pii_columns={
            "full_name", "address_line1", "address_line2", "additional_address",
            "agency_name",
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


def _agent_details(plan: LookupPlan, catalog: Catalog) -> SqlAttempt:
    value = _literal(plan.value.lower())
    sql = (
        "SELECT agent_code, agent_name, agent_type, designation, branch_code, role_code, "
        "joined_on, linked_customer_count, linked_loan_count "
        "FROM gold.agent_master WHERE LOWER(agent_code) = " + value +
        " ORDER BY agent_code LIMIT 20"
    )
    return _validated_attempt(
        sql, catalog=catalog,
        explanation="Current governed directory details for the requested agent code.",
        units={
            "agent_code": "text", "agent_name": "text", "agent_type": "text",
            "designation": "text", "branch_code": "text", "role_code": "text",
            "joined_on": "date", "linked_customer_count": "count",
            "linked_loan_count": "count",
        },
        pii_columns={"agent_name"},
    )


def _agent_count(catalog: Catalog) -> SqlAttempt:
    return _validated_attempt(
        "SELECT COUNT(agent_code) AS agent_count FROM gold.agent_master LIMIT 1",
        catalog=catalog,
        explanation="Count of agents in the current governed agent directory.",
        units={"agent_count": "count"},
    )


def _branch_directory(catalog: Catalog) -> SqlAttempt:
    sql = (
        "SELECT branch_code, branch_name, branch_category_name, branch_size, "
        "branch_status, opened_on FROM gold.branch_master "
        "ORDER BY branch_name, branch_code LIMIT 500"
    )
    return _validated_attempt(
        sql, catalog=catalog, explanation="Current governed branch directory.",
        units={
            "branch_code": "text", "branch_name": "text",
            "branch_category_name": "text", "branch_size": "text",
            "branch_status": "text", "opened_on": "date",
        },
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

    if effective.detail == "customer_summary":
        attempt = _customer_summary(effective, cat)
    elif effective.detail == "loan_details":
        attempt = _loan_details(effective, cat)
    elif effective.detail == "repayment_history":
        attempt = _repayment_history(effective, cat)
    elif effective.detail == "agent_details":
        attempt = _agent_details(effective, cat)
    elif effective.detail == "agent_count":
        attempt = _agent_count(cat)
    elif effective.detail == "branch_directory":
        attempt = _branch_directory(cat)
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


__all__ = ["LookupResult", "completions", "detect", "run"]
