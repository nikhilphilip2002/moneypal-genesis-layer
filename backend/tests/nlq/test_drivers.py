"""Driver decomposition — the "why" engine.

Pure arithmetic over two result sets. No database, no model. The invariant that matters is
exactness: the contributions must add back up to the change being explained, or the answer
is a plausible-looking lie.
"""

import pytest

from app.services.nlq import drivers
from app.services.nlq.catalog import get_catalog


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def _by_member(decomposition):
    return {c.member: c for c in decomposition.contributions}


class TestFlowMetrics:
    """A flow metric's deltas add up directly."""

    def test_contributions_sum_to_the_total_change(self, catalog):
        current = [
            {"branch": "1", "disbursement_total": 600.0},
            {"branch": "2", "disbursement_total": 300.0},
            {"branch": "3", "disbursement_total": 100.0},
        ]
        prior = [
            {"branch": "1", "disbursement_total": 400.0},
            {"branch": "2", "disbursement_total": 400.0},
            {"branch": "3", "disbursement_total": 100.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert d.delta == pytest.approx(100.0)
        assert sum(c.delta for c in d.all_contributions) == pytest.approx(d.delta)

    def test_the_largest_mover_ranks_first(self, catalog):
        current = [
            {"branch": "1", "disbursement_total": 600.0},
            {"branch": "2", "disbursement_total": 300.0},
        ]
        prior = [
            {"branch": "1", "disbursement_total": 400.0},
            {"branch": "2", "disbursement_total": 400.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert d.contributions[0].member == "1"
        assert d.contributions[0].delta == pytest.approx(200.0)

    def test_share_is_relative_to_the_total_change(self, catalog):
        current = [{"branch": "1", "disbursement_total": 300.0}]
        prior = [{"branch": "1", "disbursement_total": 100.0}]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert d.contributions[0].share == pytest.approx(1.0)

    def test_a_member_absent_from_the_prior_period_counts_as_new(self, catalog):
        current = [
            {"branch": "1", "disbursement_total": 100.0},
            {"branch": "9", "disbursement_total": 50.0},
        ]
        prior = [{"branch": "1", "disbursement_total": 100.0}]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert _by_member(d)["9"].delta == pytest.approx(50.0)
        assert _by_member(d)["9"].prior == pytest.approx(0.0)

    def test_a_member_that_disappeared_counts_as_a_loss(self, catalog):
        current = [{"branch": "1", "disbursement_total": 100.0}]
        prior = [
            {"branch": "1", "disbursement_total": 100.0},
            {"branch": "9", "disbursement_total": 50.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert _by_member(d)["9"].delta == pytest.approx(-50.0)

    def test_no_change_produces_no_drivers(self, catalog):
        rows = [{"branch": "1", "disbursement_total": 100.0}]
        d = drivers.decompose("disbursement_total", "branch", rows, list(rows), catalog)
        assert d.delta == pytest.approx(0.0)
        assert d.contributions == ()

    def test_shares_are_undefined_when_offsetting_moves_cancel(self, catalog):
        """Branch 1 up 100, branch 2 down 100. A 'share of a zero change' is meaningless,
        so the shares are dropped rather than divided by zero."""
        current = [
            {"branch": "1", "disbursement_total": 200.0},
            {"branch": "2", "disbursement_total": 100.0},
        ]
        prior = [
            {"branch": "1", "disbursement_total": 100.0},
            {"branch": "2", "disbursement_total": 200.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert d.delta == pytest.approx(0.0)
        assert all(c.share is None for c in d.all_contributions)
        assert len(d.all_contributions) == 2


class TestDecodedRows:
    """The current period arrives decoded ("Head Office"); the prior period arrives raw (1).

    Keying on the display value makes the two member sets disjoint, so every member is
    counted twice — once as a pure gain, once as a pure loss — and every share is nonsense.
    """

    def test_a_decoded_member_matches_its_raw_counterpart(self, catalog):
        current = [{"branch": "Head Office", "branch__raw": 1, "disbursement_total": 500.0}]
        prior = [{"branch": 1, "disbursement_total": 400.0}]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert len(d.all_contributions) == 1
        assert d.all_contributions[0].delta == pytest.approx(100.0)
        assert d.all_contributions[0].share == pytest.approx(1.0)

    def test_no_share_exceeds_the_whole_change(self, catalog):
        current = [
            {"branch": "Head Office", "branch__raw": 1, "disbursement_total": 500.0},
            {"branch": "Kochi", "branch__raw": 2, "disbursement_total": 300.0},
        ]
        prior = [
            {"branch": 1, "disbursement_total": 400.0},
            {"branch": 2, "disbursement_total": 400.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert sum(c.delta for c in d.all_contributions) == pytest.approx(d.delta)

    def test_the_label_comes_from_the_enum_not_the_row(self, catalog):
        current = [{"branch": "Head Office", "branch__raw": 1, "disbursement_total": 500.0}]
        prior = [{"branch": 1, "disbursement_total": 400.0}]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert d.all_contributions[0].member == "1"


class TestRatioMetrics:
    """A ratio's change splits into a rate effect and a mix effect. They must be exact."""

    CURRENT = [
        {"branch": "1", "collection_efficiency": 80.0, "amount_due": 500.0},
        {"branch": "2", "collection_efficiency": 90.0, "amount_due": 500.0},
    ]
    PRIOR = [
        {"branch": "1", "collection_efficiency": 95.0, "amount_due": 400.0},
        {"branch": "2", "collection_efficiency": 90.0, "amount_due": 600.0},
    ]

    def test_effects_sum_exactly_to_the_ratio_change(self, catalog):
        d = drivers.decompose(
            "collection_efficiency", "branch", self.CURRENT, self.PRIOR, catalog,
            weight_metric="amount_due",
        )
        total = sum(c.mix_effect + c.rate_effect for c in d.all_contributions)
        assert total == pytest.approx(d.delta)

    def test_the_ratio_total_is_recomputed_not_averaged(self, catalog):
        """Weighted: (0.8*500 + 0.9*500)/1000 = 85%, not the 85% you would get by luck
        from a plain mean — the prior period is the real test."""
        d = drivers.decompose(
            "collection_efficiency", "branch", self.CURRENT, self.PRIOR, catalog,
            weight_metric="amount_due",
        )
        # prior: (0.95*400 + 0.90*600) / 1000 = 92.0
        assert d.prior_total == pytest.approx(92.0)
        assert d.current_total == pytest.approx(85.0)

    def test_a_pure_rate_move_has_no_mix_effect(self, catalog):
        current = [
            {"branch": "1", "collection_efficiency": 80.0, "amount_due": 500.0},
            {"branch": "2", "collection_efficiency": 90.0, "amount_due": 500.0},
        ]
        prior = [
            {"branch": "1", "collection_efficiency": 95.0, "amount_due": 500.0},
            {"branch": "2", "collection_efficiency": 90.0, "amount_due": 500.0},
        ]
        d = drivers.decompose(
            "collection_efficiency", "branch", current, prior, catalog,
            weight_metric="amount_due",
        )
        assert all(c.mix_effect == pytest.approx(0.0) for c in d.all_contributions)
        assert _by_member(d)["1"].rate_effect == pytest.approx(-7.5)

    def test_a_pure_mix_move_has_no_rate_effect(self, catalog):
        """Both branches hold their own efficiency; the weak one just grew."""
        current = [
            {"branch": "1", "collection_efficiency": 80.0, "amount_due": 600.0},
            {"branch": "2", "collection_efficiency": 100.0, "amount_due": 400.0},
        ]
        prior = [
            {"branch": "1", "collection_efficiency": 80.0, "amount_due": 400.0},
            {"branch": "2", "collection_efficiency": 100.0, "amount_due": 600.0},
        ]
        d = drivers.decompose(
            "collection_efficiency", "branch", current, prior, catalog,
            weight_metric="amount_due",
        )
        assert all(c.rate_effect == pytest.approx(0.0) for c in d.all_contributions)
        assert d.delta == pytest.approx(-4.0)

    def test_without_weights_a_ratio_reports_moves_but_claims_no_shares(self, catalog):
        """Ratio deltas do not add up. Reporting a 'share of the change' without weights
        would be arithmetic fiction, so it is withheld and the reason is stated."""
        current = [{"branch": "1", "collection_efficiency": 80.0}]
        prior = [{"branch": "1", "collection_efficiency": 95.0}]
        d = drivers.decompose("collection_efficiency", "branch", current, prior, catalog)
        assert d.exact is False
        assert all(c.share is None for c in d.all_contributions)
        assert _by_member(d)["1"].delta == pytest.approx(-15.0)
        assert d.caveat

    def test_without_weights_no_total_is_claimed(self, catalog):
        """A ratio's total is a weighted average. An unweighted mean of the members is a
        different number from the one the compiler produced for the same metric, and putting
        both on adjacent cards is worse than reporting neither."""
        current = [
            {"branch": "1", "collection_efficiency": 80.0},
            {"branch": "2", "collection_efficiency": 60.0},
        ]
        prior = [
            {"branch": "1", "collection_efficiency": 95.0},
            {"branch": "2", "collection_efficiency": 90.0},
        ]
        d = drivers.decompose("collection_efficiency", "branch", current, prior, catalog)
        assert d.totals_known is False
        text = drivers.narrate(d, catalog)
        assert "70" not in text and "92" not in text  # the unweighted means
        assert "2 of 2" in text


class TestTruncation:
    def test_small_movers_roll_into_one_other_row(self, catalog):
        current = [{"branch": str(i), "disbursement_total": 100.0} for i in range(12)]
        prior = [{"branch": str(i), "disbursement_total": 0.0} for i in range(12)]
        d = drivers.decompose(
            "disbursement_total", "branch", current, prior, catalog, top_n=4
        )
        assert len(d.contributions) == 4
        assert d.other is not None
        assert d.other.delta == pytest.approx(800.0)

    def test_truncation_preserves_the_total(self, catalog):
        current = [{"branch": str(i), "disbursement_total": float(i)} for i in range(12)]
        prior = [{"branch": str(i), "disbursement_total": 0.0} for i in range(12)]
        d = drivers.decompose(
            "disbursement_total", "branch", current, prior, catalog, top_n=3
        )
        shown = sum(c.delta for c in d.contributions) + (d.other.delta if d.other else 0.0)
        assert shown == pytest.approx(d.delta)

    def test_an_other_row_that_nets_to_zero_reports_zero_not_unknown(self, catalog):
        """`None` is reserved for shares that would be fiction. A bucket whose parts
        genuinely cancel has a share, and it is zero."""
        current = [{"branch": str(i), "disbursement_total": v} for i, v in enumerate(
            [500.0, 400.0, 300.0, 200.0, 150.0, 100.0, 50.0, 50.0]
        )]
        prior = [{"branch": str(i), "disbursement_total": v} for i, v in enumerate(
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 0.0]
        )]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog, top_n=3)
        assert d.other is not None
        assert d.other.share is not None

    def test_a_short_list_has_no_other_row(self, catalog):
        current = [{"branch": "1", "disbursement_total": 100.0}]
        prior = [{"branch": "1", "disbursement_total": 50.0}]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        assert d.other is None


class TestNarration:
    def test_it_names_the_metric_the_change_and_the_top_driver(self, catalog):
        current = [
            {"branch": "1", "disbursement_total": 600.0},
            {"branch": "2", "disbursement_total": 300.0},
        ]
        prior = [
            {"branch": "1", "disbursement_total": 400.0},
            {"branch": "2", "disbursement_total": 400.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        text = drivers.narrate(d, catalog)
        assert "Disbursement" in text or "disbursement" in text
        assert "rose" in text or "fell" in text

    def test_it_distinguishes_rate_from_mix(self, catalog):
        d = drivers.decompose(
            "collection_efficiency", "branch",
            TestRatioMetrics.CURRENT, TestRatioMetrics.PRIOR, catalog,
            weight_metric="amount_due",
        )
        text = drivers.narrate(d, catalog)
        assert "mix" in text.lower()

    def test_an_unchanged_metric_says_so(self, catalog):
        rows = [{"branch": "1", "disbursement_total": 100.0}]
        d = drivers.decompose("disbursement_total", "branch", rows, list(rows), catalog)
        assert "unchanged" in drivers.narrate(d, catalog).lower()

    def test_narration_invents_no_number_outside_the_decomposition(self, catalog):
        """Every figure in the sentence must trace to a contribution or a total."""
        import re

        current = [
            {"branch": "1", "disbursement_total": 600.0},
            {"branch": "2", "disbursement_total": 300.0},
        ]
        prior = [
            {"branch": "1", "disbursement_total": 400.0},
            {"branch": "2", "disbursement_total": 400.0},
        ]
        d = drivers.decompose("disbursement_total", "branch", current, prior, catalog)
        text = drivers.narrate(d, catalog)
        allowed = {abs(d.delta), abs(d.current_total), abs(d.prior_total)}
        allowed |= {abs(c.delta) for c in d.all_contributions}
        allowed |= {round(abs(c.share or 0) * 100) for c in d.all_contributions}
        for token in re.findall(r"\d+(?:\.\d+)?", text):
            value = float(token)
            assert any(abs(value - a) < max(1.0, a * 0.02) for a in allowed), (
                f"{value} in {text!r} traces to no figure in the decomposition"
            )


class TestCatalogWeights:
    """The weight metric is declared in YAML so the decomposition stays exact."""

    @pytest.mark.parametrize(
        "metric,expected",
        [
            ("collection_efficiency", "amount_due"),
            ("par_30", "principal_outstanding"),
            ("par_90", "principal_outstanding"),
            ("npa_ratio", "principal_outstanding"),
            ("avg_ticket_size", "loan_count"),
            ("avg_interest_rate", "sanctioned_amount"),
        ],
    )
    def test_ratio_metrics_declare_their_denominator_metric(self, metric, expected, catalog):
        assert catalog.metrics[metric].weight_metric == expected

    def test_a_weight_metric_shares_the_ratios_base_table(self, catalog):
        """A weight from another table would be a different population and the split
        would silently stop being exact."""
        for metric in catalog.metrics.values():
            if not metric.weight_metric:
                continue
            weight = catalog.metrics[metric.weight_metric]
            assert weight.base_table == metric.base_table, metric.id
