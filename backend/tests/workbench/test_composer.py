"""Claim-level grounding (Phase E): numeric claims are candidates from a regex, but the
verified fact set and its governed derivations are the oracle. Nothing here forbids
recommendations or replaces prose; it maps each figure to a fact or reports it."""

from __future__ import annotations

from decimal import Decimal

from app.services.workbench import calculations, composer, facts
from app.services.workbench.facts import Fact
from app.services.workbench.results import ToolResult


def _fact(fact_id, value, unit="inr", period="FY26", field=None):
    return Fact(
        id=fact_id, label=fact_id, value=Decimal(str(value)), display_value=str(value),
        unit=unit, source="db", card_type="chart", row=0, field=field or fact_id,
        period=period,
    )


def _collections_result():
    return ToolResult(
        source="db", card_type="chart",
        payload={
            "columns": [
                {"name": "month", "label": "Month", "unit": "text"},
                {"name": "collected", "label": "Collected", "unit": "inr"},
                {"name": "demanded", "label": "Demanded", "unit": "inr"},
            ],
            "subtitle": "last 2 months",
            "rows": [
                {"month": "2026-07", "collected": 1_000_000, "demanded": 1_250_000},
                {"month": "2026-08", "collected": 1_200_000, "demanded": 1_300_000},
            ],
        },
    )


class TestNumericClaims:
    def test_claims_carry_scale_unit_and_tolerance(self):
        claims = composer.numeric_claims(
            "Collections rose 20% to ₹12 lakh (Rs 1,200,000; 0.12 crore) in 14 days."
        )
        by_text = {claim.text: claim for claim in claims}
        assert by_text["20%"].unit == "percent" and by_text["20%"].value == 20
        assert by_text["12 lakh"].unit == "inr" and by_text["12 lakh"].value == 1_200_000
        assert by_text["12 lakh"].tolerance == Decimal(50000)
        assert by_text["1,200,000"].value == 1_200_000
        assert by_text["1,200,000"].tolerance == Decimal("0.5")
        assert by_text["0.12 crore"].value == 1_200_000
        # Only magnitude words extend the claim text; a unit word tags it.
        assert by_text["14"].unit == "days"

    def test_dates_periods_and_list_markers_are_not_claims(self):
        text = "1. FY26 collections improved.\n2) Dated 2026-08-31 and 12/08/2026, FY 2024-25."
        assert composer.numeric_claims(text) == []


class TestValidateClaims:
    def test_rounding_and_thousands_separators_are_tolerated(self):
        ledger = [_fact("par", "4.19", "percent"), _fact("book", "1234567.4", "inr")]
        ok = composer.validate_claims("PAR is 4.2% on a ₹1,234,567 book.", "", ledger)
        assert ok.ok
        assert [fact.id for _claim, fact in ok.supported] == ["par", "book"]

    def test_percent_claims_match_ratio_facts_and_vice_versa(self):
        assert composer.validate_claims("Rate 4.2%.", "", [_fact("r", "0.042", "ratio")]).ok
        assert composer.validate_claims("Ratio 0.042.", "", [_fact("r", "4.2", "percent")]).ok
        assert not composer.validate_claims("Rate 42%.", "", [_fact("r", "0.042", "ratio")]).ok

    def test_lakh_and_crore_claims_round_to_the_fact_magnitude(self):
        ledger = [_fact("book", "12345678", "inr")]
        assert composer.validate_claims("Book of ₹1.23 crore.", "", ledger).ok
        assert composer.validate_claims("Book of Rs 123.5 lakh.", "", ledger).ok
        assert composer.validate_claims("Book of 1.2 cr.", "", ledger).ok
        assert composer.validate_claims("Book of ₹1.3 crore.", "", ledger).unsupported_texts == [
            "1.3 crore"
        ]

    def test_wrong_unit_or_period_is_unsupported(self):
        ledger = [_fact("par", "4.2", "percent", period="FY26")]
        assert composer.validate_claims("PAR was 4.2% in FY26.", "", ledger).ok
        assert not composer.validate_claims("PAR was Rs 4.2 in FY26.", "", ledger).ok
        assert not composer.validate_claims("PAR was 4.2% in FY25.", "", ledger).ok

    def test_evidence_numbers_support_claims_but_are_not_cited_facts(self):
        validation = composer.validate_claims("Market grew 6.5%.", "GDP grew 6.5% in FY26.")
        assert validation.ok
        assert validation.cited_facts == []

    def test_correct_derived_percentage_from_two_ledger_facts_passes(self):
        fact_set = calculations.fact_set(facts.from_results([_collections_result()]))
        validation = composer.validate_claims(
            "Collections rose 20% to ₹12 lakh from ₹10 lakh; the collection rate was "
            "92.3% and 2026-08 ranked 1 of the two months.",
            "", fact_set,
        )
        assert validation.ok
        cited = {fact.operation for fact in validation.cited_facts}
        assert {"percent_change", "rate"} <= cited
        change = next(f for f in validation.cited_facts if f.operation == "percent_change")
        assert change.operands == ("db:0:1:collected", "db:0:0:collected")
        assert change.unit == "percent" and change.formula

    def test_signless_change_matches_either_direction(self):
        fact_set = calculations.fact_set(facts.from_results([_collections_result()]))
        assert composer.validate_claims("Collections fell by ₹2 lakh.", "", fact_set).ok
        assert composer.validate_claims("Collections rose by 200,000.", "", fact_set).ok

    def test_invented_figure_is_the_only_unsupported_claim(self):
        fact_set = calculations.fact_set(facts.from_results([_collections_result()]))
        validation = composer.validate_claims(
            "Collections rose 20%. Invented PAR is 9.9%. Consider a follow-up drive.",
            "", fact_set,
        )
        assert validation.unsupported_texts == ["9.9%"]
        assert composer.numbers_are_grounded("Collections rose 20%.", "", fact_set)


class TestRemoveUnsupportedClaims:
    def test_only_the_offending_sentence_or_bullet_goes(self):
        text = (
            "Collections rose 20% to ₹12 lakh.\n- Collection rate was 92.3%.\n"
            "- Invented PAR is 9.9%.\nRecommend a branch review."
        )
        fact_set = calculations.fact_set(facts.from_results([_collections_result()]))
        validation = composer.validate_claims(text, "", fact_set)
        cleaned, removed = composer.remove_unsupported_claims(text, validation.unsupported)
        assert cleaned == (
            "Collections rose 20% to ₹12 lakh.\n- Collection rate was 92.3%.\n"
            "Recommend a branch review."
        )
        assert removed == ["- Invented PAR is 9.9%."]

    def test_compatibility_wrapper_keeps_ordered_markers(self):
        text = "1. Portfolio quality improved. Invented PAR is 9.9%. Collections stayed stable."
        assert composer.remove_unsupported_numeric_sentences(text, ["9.9%"]) == (
            "1. Portfolio quality improved. Collections stayed stable."
        )


class TestDerivedFacts:
    def test_every_derived_fact_carries_provenance(self):
        ledger = facts.from_results([_collections_result()])
        derived = calculations.derived_facts(ledger)
        assert derived
        ids = {fact.id for fact in ledger}
        for fact in derived:
            assert fact.source == "calculation" and fact.operation and fact.formula
            assert fact.unit
            assert fact.operands
            for operand in fact.operands:
                assert operand in ids or operand.startswith("calc:total:")
        operations = {fact.operation for fact in derived}
        assert operations == {"total", "share", "rank", "difference", "percent_change", "rate"}

    def test_derivations_are_deterministic_and_bounded(self):
        ledger = facts.from_results([_collections_result()])
        assert calculations.derived_facts(ledger) == calculations.derived_facts(ledger)
        big = [_fact(f"f{i}", i + 1, "count") for i in range(200)]
        assert len(calculations.derived_facts(big)) <= calculations.MAX_DERIVED_FACTS

    def test_non_additive_units_are_ranked_but_not_totalled(self):
        # Chart facts form a series per column, so both rows share the field ``par``.
        derived = calculations.derived_facts([
            _fact("db:0:0:par", "4.2", "percent", field="par"),
            _fact("db:0:1:par", "5.1", "percent", field="par"),
        ])
        assert {fact.operation for fact in derived} == {"rank", "difference", "percent_change"}


class TestFactRendering:
    def test_facts_text_is_bounded_json_lines_with_derived_provenance(self):
        fact_set = calculations.fact_set(facts.from_results([_collections_result()]))
        block = composer.facts_text(fact_set)
        lines = block.splitlines()
        # Source facts come first and always fit; derived facts fill the remaining budget.
        source_count = sum(1 for fact in fact_set if fact.source != "calculation")
        assert len(lines) > source_count
        assert len(block) <= composer.MAX_FACTS_CHARS
        assert '"operands":' in block and '"formula":' in block
        assert all(len(line) for line in lines)
        assert len(composer.facts_text(fact_set, limit=200)) <= 200

    def test_repair_message_names_claims_and_facts(self):
        message = composer.repair_message(["9.9%", "₹7 crore"], '{"id":"db:0:0:x"}')
        assert '"9.9%"; "₹7 crore"' in message
        assert "VERIFIED FACTS" in message and '{"id":"db:0:0:x"}' in message
        assert "Rewrite the answer once" in message
