"""Role-aware PII context for model-generated, validated SQL."""

from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import RetrievalResult
from app.services.nlq.text_to_sql import (
    NAME_PII_COLUMN_IDS,
    _context_block,
    _infer_column_units,
    _system_prompt,
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
        hits, get_catalog(), tables=["gold.semantic_msme_lead"],
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
