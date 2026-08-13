"""Role-aware PII context for named-borrower text-to-SQL questions."""

from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import RetrievalResult
from app.services.nlq.text_to_sql import NAME_PII_COLUMN_IDS, _context_block, _system_prompt


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
