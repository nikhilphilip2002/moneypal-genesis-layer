"""Contract tests for the Gold-only GICC portfolio graph."""

from datetime import date
from pathlib import Path

import pytest

from app.api.routes import admin
from app.services.curiosity_graph import BRANCH_SQL, _metrics, _where


def test_metric_contract_keeps_numeric_values_and_uses_exposure_ratios():
    metrics = _metrics([
        100, 90, 80, 20_000_000, 18_000_000, 10_000_000, 500_000,
        1_000_000, 250_000, 95, date(2026, 7, 31),
    ])

    assert metrics["account_count"] == 100
    assert metrics["borrower_count"] == 80
    assert metrics["principal_outstanding"] == 10_000_000
    assert metrics["par30_ratio"] == 10.0
    assert metrics["npa_ratio"] == 2.5
    assert metrics["risk_coverage_pct"] == 95.0
    assert metrics["loan_data_as_of"] == "2026-07-31"


def test_branch_filter_prefers_reporting_branch_with_documented_application_fallback():
    where, params = _where({"product_code": "16", "branch_code": "4"})

    assert BRANCH_SQL in where
    assert "reporting_branch_code" in where
    assert "application_branch_code" in where
    assert params == ["1", "16", "4"]


def test_unassigned_agent_is_a_real_filter_not_an_empty_string_comparison():
    where, params = _where({"agent_code": "UNASSIGNED"})

    assert "NULLIF(BTRIM(l.agent_code::text), '') IS NULL" in where
    assert params == ["1"]


def test_graph_service_does_not_query_silver_or_bronze_views():
    source = Path(__file__).parents[1] / "app/services/curiosity_graph.py"
    text = source.read_text(encoding="utf-8")

    assert "gold.semantic_loan_account" in text
    assert "gold.semantic_portfolio_snapshot" in text
    assert "gold.semantic_branch" in text
    assert "silver." not in text
    assert "bronze." not in text


def test_admin_route_maps_legacy_level_names_to_the_gold_contract(monkeypatch):
    seen = {}

    def fake_graph(**kwargs):
        seen.update(kwargs)
        return {"version": 2}

    monkeypatch.setattr(admin, "get_curiosity_graph", fake_graph)
    response = admin.db_schema(view_level="zonal", zonal_id="product:16", limit=20)

    assert response == {"version": 2}
    assert seen["level"] == "product"
    assert seen["product_code"] == "16"
    assert seen["limit"] == 20


@pytest.mark.parametrize("weight", ["borrowers", "outstanding", "accounts"])
def test_admin_route_preserves_supported_weighting_modes(monkeypatch, weight):
    monkeypatch.setattr(admin, "get_curiosity_graph", lambda **kwargs: kwargs)

    response = admin.db_schema(level="portfolio", weight_by=weight)

    assert response["weight_by"] == weight


def test_where_filters_support_tenure_and_loan_size():
    where, params = _where({
        "agent_code": "AGNT45",
        "scheme_code": "1616",
        "tenure_band": "tenure_25_36",
        "loan_size_bucket": "bucket_2l_5l",
    })

    assert "l.agent_code::text = %s" in where
    assert "l.number_of_emis > 24 AND l.number_of_emis <= 36" in where
    assert "l.sanction_amount >= 200000 AND l.sanction_amount < 500000" in where
    assert "AGNT45" in params
    assert "1616" in params


def test_admin_route_passes_tenure_and_loan_size_buckets(monkeypatch):
    seen = {}

    def fake_graph(**kwargs):
        seen.update(kwargs)
        return {"version": 2}

    monkeypatch.setattr(admin, "get_curiosity_graph", fake_graph)
    response = admin.db_schema(
        level="loan_size",
        agent_code="AGNT45",
        scheme_code="1616",
        tenure_band="tenure_25_36",
        loan_size_bucket="bucket_2l_5l",
    )

    assert response == {"version": 2}
    assert seen["level"] == "loan_size"
    assert seen["tenure_band"] == "tenure_25_36"
    assert seen["loan_size_bucket"] == "bucket_2l_5l"


def test_admin_customer_details_endpoint(monkeypatch):
    monkeypatch.setattr(
        admin,
        "get_customer_360_details",
        lambda customer_id: {"profile": {"customer_id": customer_id}, "loans": [], "repayment_history": []},
    )

    result = admin.customer_details("8")
    assert result["profile"]["customer_id"] == "8"
    assert "loans" in result
    assert "repayment_history" in result


def test_admin_route_passes_customer_level(monkeypatch):
    seen = {}

    def fake_graph(**kwargs):
        seen.update(kwargs)
        return {"version": 2}

    monkeypatch.setattr(admin, "get_curiosity_graph", fake_graph)
    response = admin.db_schema(
        level="customer",
        customer_id="121",
    )

    assert response == {"version": 2}
    assert seen["level"] == "customer"
    assert seen["customer_id"] == "121"


