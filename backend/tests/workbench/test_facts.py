from dataclasses import replace
from decimal import Decimal

import pytest

from app.services.workbench import calculations, composer, facts
from app.services.workbench.facts import Fact
from app.services.workbench.results import ToolResult


def _fact(fact_id, value, unit="inr", period="FY26"):
    return Fact(
        id=fact_id, label=fact_id, value=Decimal(str(value)), display_value=str(value),
        unit=unit, source="db", card_type="chart", row=0, field=fact_id, period=period,
    )


def test_chart_rows_become_verified_typed_facts():
    result = ToolResult(
        source="db", card_type="chart",
        payload={
            "columns": [
                {"name": "branch", "label": "Branch", "unit": "text"},
                {"name": "value", "label": "Outstanding", "unit": "inr"},
            ],
            "subtitle": "this_month",
            "rows": [{"branch": "A", "value": 1200.5}],
        },
    )
    ledger = facts.from_results([result])
    assert len(ledger) == 1
    assert ledger[0].value == Decimal("1200.5")
    assert ledger[0].verified is True
    assert ledger[0].period == "this_month"
    assert ledger[0].dimensions == (("branch", "A"),)


def test_derived_difference_and_share_carry_provenance():
    left, right = _fact("left", 120), _fact("right", 100)
    delta = calculations.derive("difference", left, right, fact_id="delta", label="Change")
    share = calculations.derive("share", left, right, fact_id="share", label="Share")
    assert delta.value == Decimal("20")
    assert delta.operands == ("left", "right")
    assert share.value == Decimal("120.0")
    assert share.unit == "percent"


def test_calculation_rejects_zero_and_mixed_units():
    with pytest.raises(calculations.CalculationError, match="division by zero"):
        calculations.derive("ratio", _fact("a", 1), _fact("b", 0), fact_id="x", label="x")
    with pytest.raises(calculations.CalculationError, match="units"):
        calculations.derive(
            "difference", _fact("a", 1), _fact("b", 1, "count"), fact_id="x", label="x",
        )
    with pytest.raises(calculations.CalculationError, match="periods"):
        calculations.derive(
            "difference", _fact("a", 1, period=""), _fact("b", 1),
            fact_id="x", label="x",
        )


def test_claim_validation_accepts_ledger_and_rejects_invention():
    ledger = [_fact("par", "4.2", "percent")]
    assert composer.numbers_are_grounded("PAR is 4.2%.", "", ledger)
    assert composer.numbers_are_grounded("PAR is 4.20%.", "", ledger)
    assert composer.unsupported_numbers("PAR is 4.3%.", "", ledger) == ["4.3%"]


def test_analysis_findings_become_facts_with_period_and_filters():
    result = ToolResult(
        source="db", card_type="analysis",
        payload={
            "findings": [{
                "step_id": "par", "label": "PAR 30", "value": 4.2, "unit": "percent",
                "spec": {
                    "period": {"relative": "this_month"},
                    "filters": [{"field": "branch", "op": "eq", "value": "Aluva"}],
                },
            }],
        },
    )
    fact = facts.from_results([result])[0]
    assert fact.period == "this_month"
    assert fact.dimensions == (("branch", "Aluva"),)


def test_weighted_average_is_deterministic_and_provenanced():
    values = [
        _fact("v1", 10, "percent"),
        _fact("v2", 20, "percent"),
    ]
    weights = [
        _fact("w1", 1, "count"),
        _fact("w2", 3, "count"),
    ]
    derived = calculations.weighted_average(
        values, weights, fact_id="weighted", label="Weighted rate",
    )
    assert derived.value == Decimal("17.5")
    assert derived.operands == ("v1", "w1", "v2", "w2")


def test_ordered_markers_are_allowed_and_invalid_numeric_sentence_is_removed():
    text = "1. Portfolio quality improved. Invented PAR is 9.9%. Collections stayed stable."
    assert composer.unsupported_numbers(text, "") == ["9.9%"]
    assert composer.remove_unsupported_numeric_sentences(text, ["9.9%"]) == (
        "1. Portfolio quality improved. Collections stayed stable."
    )


def test_claim_validation_rejects_wrong_unit_and_explicit_wrong_period():
    ledger = [replace(_fact("par", "4.2", "percent"), period="FY26")]
    assert composer.numbers_are_grounded("PAR was 4.2% in FY26.", "", ledger)
    assert not composer.numbers_are_grounded("PAR was Rs 4.2 in FY26.", "", ledger)
    assert not composer.numbers_are_grounded("PAR was 4.2% in FY25.", "", ledger)
