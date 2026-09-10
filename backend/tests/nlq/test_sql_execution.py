"""Metadata helpers for governed, already-validated SQL."""

from app.services.nlq.catalog import get_catalog
from app.services.nlq.sql_execution import infer_column_units


def test_aggregate_alias_inherits_catalog_unit():
    units = infer_column_units(
        "SELECT business_type, SUM(amount_requested) AS total_requested_amount, "
        "SUM(security_value) AS total_security_value FROM gold.business_loan_leads "
        "GROUP BY business_type LIMIT 5000",
        ["gold.business_loan_leads"],
        get_catalog(),
    )
    assert units == {
        "business_type": "text",
        "total_requested_amount": "inr",
        "total_security_value": "inr",
    }
