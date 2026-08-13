"""Role-aware PII context for named-borrower text-to-SQL questions."""

from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import RetrievalResult
from app.services.nlq.charts import build_from_rows
from app.services.nlq.contracts import Lineage
from app.services.nlq.executor import QueryResult
from app.services.nlq.text_to_sql import (
    NAME_PII_COLUMN_IDS,
    _context_block,
    _named_borrower_disbursed_attempt,
    _named_borrower_principal_attempt,
    _system_prompt,
    named_borrower_disbursed_name,
    named_borrower_principal_name,
)


def _loan_context(*, allow_pii: bool) -> str:
    hits = RetrievalResult(tables=["silver.loan_account_master"], mode="lexical")
    return _context_block(hits, get_catalog(), allow_pii=allow_pii)


def test_authorized_context_exposes_borrower_name_but_not_other_pii():
    context = _loan_context(allow_pii=True)

    assert "gnlnac_cust_name" in context
    assert "gnlnac_pri_repay_amt" in context
    assert "indcif_dob" not in context
    assert "indcif_phouse_name" not in context


def test_unauthorized_context_hides_borrower_name():
    assert "gnlnac_cust_name" not in _loan_context(allow_pii=False)


def test_prompt_lifts_only_the_name_lookup_prohibition_for_authorized_roles():
    authorized = _system_prompt(True)
    unauthorized = _system_prompt(False)

    assert "may use listed borrower-name columns" in authorized
    assert "Never reference customer names" in unauthorized
    assert "Never reference dates of birth" in authorized


def test_name_only_allowlist_excludes_sensitive_customer_attributes():
    assert NAME_PII_COLUMN_IDS == {
        "loan.customer_name",
        "customer.first_name",
        "customer.last_name",
    }


def test_named_borrower_principal_uses_reviewed_columns_without_an_llm():
    attempt = _named_borrower_principal_attempt(
        "principle amount paid by sheelavati",
        get_catalog(),
        allow_pii=True,
    )

    assert attempt is not None and attempt.validated
    assert attempt.model == "deterministic"
    assert "gnlnac_pri_repay_amt" in attempt.sql
    assert "gnlnac_cust_name" in attempt.sql
    assert "gnlnac_prin" not in attempt.sql
    assert "LIKE 'shelavati' || '%'" in attempt.sql
    assert "GROUP BY" in attempt.sql
    assert attempt.column_units["principal_repaid"] == "inr"
    assert attempt.pii_columns == ["gnlnac_cust_name"]


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
    assert "gnlnac_lndisb_amt" in attempt.sql
    assert "gnlnac_cust_name" in attempt.sql
    assert "LIKE 'shelavati' || '%'" in attempt.sql
    assert attempt.column_units["disbursed_amount"] == "inr"


def test_named_borrower_disbursement_stays_blocked_for_unauthorized_roles():
    assert _named_borrower_disbursed_attempt(
        "amount disbursed to Sheelavati",
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
