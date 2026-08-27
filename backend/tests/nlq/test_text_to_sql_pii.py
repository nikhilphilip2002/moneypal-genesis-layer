"""Role-aware PII context for named-borrower text-to-SQL questions."""

from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import RetrievalResult
from app.services.nlq.charts import build_from_rows
from app.services.nlq.contracts import Lineage
from app.services.nlq.executor import QueryResult
from app.services.nlq.text_to_sql import (
    NAME_PII_COLUMN_IDS,
    _agent_directory_attempt,
    _context_block,
    _infer_column_units,
    _named_borrower_disbursed_attempt,
    _named_borrower_principal_attempt,
    _system_prompt,
    named_borrower_disbursed_name,
    named_borrower_principal_name,
)


def _loan_context(*, allow_pii: bool) -> str:
    hits = RetrievalResult(tables=["gold.semantic_loan_account"], mode="lexical")
    return _context_block(hits, get_catalog(), allow_pii=allow_pii)


def test_authorized_context_exposes_governed_borrower_fields():
    context = _loan_context(allow_pii=True)

    assert "customer_name" in context
    assert "principal_repaid" in context
    assert "date_of_birth" not in context


def test_unauthorized_context_hides_borrower_name():
    assert "customer_name" not in _loan_context(allow_pii=False)


def test_planner_table_hint_limits_generated_sql_context():
    hits = RetrievalResult(
        tables=["gold.semantic_msme_lead", "gold.semantic_loan_account"], mode="lexical"
    )
    context = _context_block(
        hits,
        get_catalog(),
        tables=["gold.semantic_msme_lead"],
    )
    assert "gold.semantic_msme_lead" in context
    assert "gold.semantic_loan_account" not in context


def test_prompt_allows_only_explicitly_needed_pii_for_authorized_roles():
    authorized = _system_prompt(True)
    unauthorized = _system_prompt(False)

    assert "may use listed PII columns" in authorized
    assert "Never reference customer names" in unauthorized
    assert "never broaden a person-level query" in authorized


def test_pii_allowlist_is_curated_and_gold_catalog_backed():
    assert "loan.customer_name" in NAME_PII_COLUMN_IDS
    assert "agent.name" in NAME_PII_COLUMN_IDS
    assert "customer.pan" in NAME_PII_COLUMN_IDS


def test_named_borrower_principal_uses_reviewed_columns_without_an_llm():
    attempt = _named_borrower_principal_attempt(
        "principle amount paid by sheelavati",
        get_catalog(),
        allow_pii=True,
    )

    assert attempt is not None and attempt.validated
    assert attempt.model == "deterministic"
    assert "principal_repaid" in attempt.sql
    assert "customer_name" in attempt.sql
    assert "gold.semantic_loan_account" in attempt.sql
    assert "LIKE 'shelavati' || '%'" in attempt.sql
    assert "GROUP BY" in attempt.sql
    assert attempt.column_units["principal_repaid"] == "inr"
    assert attempt.pii_columns == ["customer_name"]


def test_named_borrower_principal_stays_blocked_for_unauthorized_roles():
    assert _named_borrower_principal_attempt(
        "principal amount paid by sheelavati",
        get_catalog(),
        allow_pii=False,
    ) is None


def test_named_borrower_disbursement_uses_reviewed_columns_without_an_llm():
    attempt = _named_borrower_disbursed_attempt(
        "loan amount disburdsed to shellavati",
        get_catalog(),
        allow_pii=True,
    )

    assert attempt is not None and attempt.validated
    assert attempt.model == "deterministic"
    assert "disbursed_amount" in attempt.sql
    assert "customer_name" in attempt.sql
    assert "gold.semantic_loan_account" in attempt.sql
    assert "LIKE 'shelavati' || '%'" in attempt.sql
    assert attempt.column_units["disbursed_amount"] == "inr"


def test_named_borrower_disbursement_stays_blocked_for_unauthorized_roles():
    assert _named_borrower_disbursed_attempt(
        "amount disbursed to Sheelavati",
        get_catalog(),
        allow_pii=False,
    ) is None


def test_agent_directory_uses_only_requested_governed_fields_without_an_llm():
    attempt = _agent_directory_attempt(
        "Show agent names, designations, branch codes and linked loan counts",
        get_catalog(),
        allow_pii=True,
    )

    assert attempt is not None and attempt.validated
    assert attempt.model == "deterministic"
    assert attempt.attempts == 0
    assert attempt.tables == ["gold.semantic_agent"]
    assert "agent_code" in attempt.sql
    assert "agent_name" in attempt.sql
    assert "designation" in attempt.sql
    assert "branch_code" in attempt.sql
    assert "linked_loan_count" in attempt.sql
    assert "mobile" not in attempt.sql
    assert "email" not in attempt.sql
    assert attempt.pii_columns == ["agent_name"]


def test_agent_contact_fields_are_included_only_when_explicitly_requested():
    attempt = _agent_directory_attempt(
        "List agent names, mobile numbers and email addresses",
        get_catalog(),
        allow_pii=True,
    )

    assert attempt is not None and attempt.validated
    assert "mobile" in attempt.sql
    assert "email" in attempt.sql
    assert attempt.pii_columns == ["agent_name", "email", "mobile"]


def test_agent_directory_stays_blocked_when_pii_is_disabled():
    assert _agent_directory_attempt(
        "Show agent names and designations",
        get_catalog(),
        allow_pii=False,
    ) is None


def test_named_borrower_literal_is_safely_quoted():
    attempt = _named_borrower_principal_attempt(
        "principal amount paid by O'Neil",
        get_catalog(),
        allow_pii=True,
    )
    assert attempt is not None
    assert "LIKE 'oneil' || '%'" in attempt.sql


def test_name_match_normalizes_th_spelling_and_keeps_ambiguous_names_separate():
    attempt = _named_borrower_principal_attempt(
        "principal amount paid by sheelavati",
        get_catalog(),
        allow_pii=True,
    )
    assert attempt is not None
    assert "REPLACE(LOWER" in attempt.sql
    assert "'th', 't'" in attempt.sql
    assert "borrower_name" in attempt.sql
    assert "GROUP BY" in attempt.sql


def test_named_borrower_intent_matcher_does_not_claim_period_questions():
    assert named_borrower_principal_name("principal paid by Sheelavati") == "Sheelavati"
    assert named_borrower_principal_name("principal paid by Sheelavati last month") is None
    assert named_borrower_disbursed_name("amount disbursed to Sheelavati") == "Sheelavati"
    assert named_borrower_disbursed_name("amount disbursed to Sheelavati last month") is None


def test_reviewed_unit_hint_renders_principal_as_inr():
    chart = build_from_rows(
        question="principal amount paid by Sheelavati",
        result=QueryResult(
            rows=[{"borrower_name": "SHEELAVATHI M K", "principal_repaid": 500000.0}],
            columns=["borrower_name", "principal_repaid"],
            status="ok",
            duration_ms=1,
            sql="SELECT 1",
            row_count=1,
        ),
        lineage=Lineage(path="text_to_sql", sql="SELECT 1"),
        unit_hints={"borrower_name": "text", "principal_repaid": "inr"},
    )

    principal = next(column for column in chart.columns if column.name == "principal_repaid")
    assert principal.unit == "inr"
    assert chart.series[0].unit == "inr"


def test_generated_aggregate_alias_inherits_catalog_unit():
    units = _infer_column_units(
        "SELECT firm_type_desc, SUM(requested_amount) AS total_requested_amount, "
        "SUM(security_value) AS total_security_value FROM gold.semantic_msme_lead "
        "GROUP BY firm_type_desc LIMIT 5000",
        ["gold.semantic_msme_lead"],
        get_catalog(),
    )
    assert units == {
        "firm_type_desc": "text",
        "total_requested_amount": "inr",
        "total_security_value": "inr",
    }
