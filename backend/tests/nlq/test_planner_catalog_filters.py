"""Catalog entity filters should never wait for, or be rewritten by, the planner LLM."""

from __future__ import annotations

import pytest

from app.services.nlq.analysis import build
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import AnalysisPlan, QuerySpecPlan
from app.services.nlq.planner import plan


class ExplodingClient:
    async def complete(self, **_kwargs):
        raise AssertionError("catalog-filtered question reached the LLM")


FILTERED_CASES = [
    ("How many total active loan accounts do we have?", "loan_count", "open_closed_status"),
    ("What is the total principal outstanding in Gold Loans?", "principal_outstanding", "product"),
    ("What is the total principal outstanding in Business and MSME Loans?", "principal_outstanding", "product"),
    ("What is the total principal outstanding in Microfinance and Retail EMI?", "principal_outstanding", "product"),
    ("What is the total principal outstanding in Aluva branch?", "principal_outstanding", "branch"),
    ("Show disbursement volume in Kozhikode branch.", "disbursement_total", "branch"),
    ("Show disbursement volume in Thripunithura branch.", "disbursement_total", "branch"),
    ("Show disbursement volume in Angamally branch.", "disbursement_total", "branch"),
    ("What is the collection efficiency for MSME Loans?", "collection_efficiency", "product"),
    ("What is the collection efficiency for Microfinance and Retail EMI?", "collection_efficiency", "product"),
    ("What is the total principal outstanding in the 31-60 DPD bucket?", "principal_outstanding", "dpd_bucket"),
    ("What is the total principal outstanding in the 61-90 DPD bucket?", "principal_outstanding", "dpd_bucket"),
    ("What is the total principal outstanding in the 90+ DPD bucket?", "principal_outstanding", "dpd_bucket"),
    ("What is the total principal outstanding in SMA-0 assets?", "principal_outstanding", "asset_class"),
    ("What is the total principal outstanding in SMA-2 assets?", "principal_outstanding", "asset_class"),
    ("How many loan accounts are classified as Standard?", "classified_account_count", "asset_class"),
    ("How many loan accounts are classified as SMA-0?", "classified_account_count", "asset_class"),
    ("How many loan accounts are classified as SMA-1?", "classified_account_count", "asset_class"),
    ("How many loan accounts are classified as SMA-2?", "classified_account_count", "asset_class"),
    ("How many loan accounts are classified as NPA?", "classified_account_count", "asset_class"),
    ("Show asset classification breakdown for Business & MSME loans.", "principal_outstanding", "product"),
    ("Show asset classification breakdown for Gold Loans.", "principal_outstanding", "product"),
    ("Show asset classification breakdown in Head Office Credit Division.", "principal_outstanding", "branch"),
    ("Show sanctioned amount in CCF Low ROI Scheme.", "sanctioned_amount", "scheme"),
    ("Show loan count in EV Retail Scheme.", "loan_count", "scheme"),
    ("Show sanctioned amount in Purchase of Two Wheelers scheme.", "sanctioned_amount", "scheme"),
    ("What is the loan volume in New Autorickshaw scheme?", "loan_count", "scheme"),
    ("Show principal outstanding in Four Wheeler Taxi / Car scheme.", "principal_outstanding", "scheme"),
    ("Show loan count in New Lorry / Bus scheme.", "loan_count", "scheme"),
    ("What is the total outstanding in Used Vehicles Under 7 Years scheme?", "principal_outstanding", "scheme"),
    ("What is the sanctioned amount in Business / Service / Industry scheme?", "sanctioned_amount", "scheme"),
    ("Show principal outstanding in Cattle loan scheme.", "principal_outstanding", "scheme"),
    ("Show loan count in Poultry / Sheep / Pigs scheme.", "loan_count", "scheme"),
    ("What is the principal outstanding in Loan Against Property schemes?", "principal_outstanding", "scheme"),
    ("Show loan count in Personal Loan scheme.", "loan_count", "scheme"),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("question", "metric", "filter_field"), FILTERED_CASES)
async def test_filtered_benchmark_questions_are_deterministic_and_compile(
    question, metric, filter_field
):
    catalog = get_catalog()
    outcome = await plan(question, catalog=catalog, client=ExplodingClient())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.model == "deterministic"
    assert outcome.attempts == 0
    assert outcome.plan.spec.metrics == [metric]
    assert filter_field in {item.field for item in outcome.plan.spec.filters}
    compiled = compile_spec(outcome.plan.spec, catalog)
    assert compiled.sql


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "analysis_id"),
    [
        (
            "Compare sanctioned amount against total disbursed amount by branch.",
            "sanctions_vs_disbursements_by_branch",
        ),
        (
            "What is the performance and volume of FTG Patharamattu Scheme?",
            "loan_segment_performance",
        ),
    ],
)
async def test_multi_metric_benchmark_questions_use_reviewed_analysis(
    question, analysis_id
):
    catalog = get_catalog()
    outcome = await plan(question, catalog=catalog, client=ExplodingClient())

    assert isinstance(outcome.plan, AnalysisPlan)
    assert outcome.plan.analysis_id == analysis_id
    assert outcome.model == "deterministic"
    analysis = build(
        outcome.plan.analysis_id,
        catalog=catalog,
        period=outcome.plan.period,
        filters=outcome.plan.filters,
    )
    for step in analysis.steps:
        assert compile_spec(step.spec, catalog).sql


@pytest.mark.anyio
async def test_named_scheme_filter_is_not_dropped_by_total_sanction_shortcut():
    outcome = await plan(
        "What is the total sanctioned amount in Purchase of Site scheme?",
        client=ExplodingClient(),
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["sanctioned_amount"]
    assert [item.model_dump() for item in outcome.plan.spec.filters] == [
        {"field": "scheme", "op": "eq", "value": "1601"}
    ]
    compiled = compile_spec(outcome.plan.spec)
    assert 'lam."scheme_code"::text = :f0' in compiled.sql
    assert compiled.params["f0"] == "1601"


def test_derived_bucket_and_account_state_filters_use_governed_expressions():
    catalog = get_catalog()
    bucket = compile_spec(
        QuerySpecPlan(
            spec={
                "metrics": ["principal_outstanding"],
                "filters": [{"field": "dpd_bucket", "op": "eq", "value": "31-60"}],
                "period": {"relative": "today"},
            },
            confidence=1.0,
        ).spec,
        catalog,
    )
    active = compile_spec(
        QuerySpecPlan(
            spec={
                "metrics": ["loan_count"],
                "filters": [
                    {"field": "open_closed_status", "op": "eq", "value": "Open"}
                ],
                "period": {"relative": "all_time"},
            },
            confidence=1.0,
        ).spec,
        catalog,
    )

    assert "WHEN portfolio.\"dpd_days\" BETWEEN 31 AND 60 THEN '31-60'" in bucket.sql
    assert "WHEN UPPER(BTRIM(COALESCE(lam.\"loan_status\", '')))" in active.sql
