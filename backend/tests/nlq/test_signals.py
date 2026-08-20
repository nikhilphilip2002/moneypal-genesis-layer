"""Standing signals: what counts as notable, and what does not.

The detectors are pure, which is the whole point — "what are the emerging issues?" becomes a
test rather than a judgement call. The bar these pin most carefully is the *lower* one: a feed
that fires on noise trains the reader to ignore it, and then the real signal arrives and gets
ignored with it.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import Signal
from app.services.signals import detectors, morning, scan, store

TODAY = date(2026, 7, 29)


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


class TestLevelShift:
    FLAT = [4.0, 4.1, 3.9, 4.0, 4.05, 3.95]

    def test_a_spike_after_a_stable_run_fires(self):
        detection = detectors.level_shift([*self.FLAT, 9.0])
        assert detection is not None
        assert detection.severity == "alert"
        assert detection.direction == "up"

    def test_an_ordinary_month_does_not(self):
        assert detectors.level_shift([*self.FLAT, 4.02]) is None

    def test_a_drop_reports_its_direction(self):
        detection = detectors.level_shift([*self.FLAT, 0.5])
        assert detection is not None and detection.direction == "down"

    def test_too_little_history_abstains(self):
        """Genesis's snapshot history starts 2026-05-22. A verdict computed from two points
        is not a weaker signal, it is a made-up one."""
        assert detectors.level_shift([4.0, 9.0]) is None
        assert detectors.level_shift([4.0, 4.1, 4.0, 9.0]) is None

    def test_a_perfectly_flat_baseline_abstains(self):
        """A zero standard deviation makes every z-score infinite. Eight months at 4.0
        moving to 4.1 is a rounding change, not a five-sigma event."""
        assert detectors.level_shift([4.0] * 8 + [4.1]) is None

    def test_missing_periods_are_skipped_not_zeroed(self):
        """A month with no rows is a gap. Treating it as zero invents a crash and then
        reports the recovery from it as a spike."""
        assert detectors.level_shift([4.0, None, 4.1, 3.9, 4.0, 4.05, 3.95, 4.0]) is None

    def test_it_reports_the_baseline_it_judged_against(self):
        """A signal saying only "PAR 30 is unusual" is one the reader has to go and check."""
        detection = detectors.level_shift([*self.FLAT, 9.0])
        assert detection is not None
        assert detection.baseline == pytest.approx(4.0, abs=0.1)


class TestTrendBreak:
    def test_a_reversal_after_a_run_fires(self):
        detection = detectors.trend_break([1.0, 2.0, 3.0, 4.0, 5.0, 4.0])
        assert detection is not None
        assert detection.direction == "down"

    def test_a_single_wobble_in_a_run_does_not(self):
        assert detectors.trend_break([1.0, 2.0, 3.0, 2.9, 4.0, 3.9]) is None

    def test_a_continuing_trend_does_not(self):
        assert detectors.trend_break([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]) is None

    def test_it_catches_what_a_z_score_misses(self):
        """A steadily drifting series has a wide standard deviation and hides its own
        inflection inside it — which is exactly when "it has turned" matters."""
        drifting = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 6.5]
        assert detectors.level_shift(drifting) is None
        assert detectors.trend_break(drifting) is not None


class TestThresholdBreach:
    def test_above_an_alert_bound_is_an_alert(self):
        detection = detectors.threshold_breach(12.0, watch_above=5.0, alert_above=10.0)
        assert detection is not None and detection.severity == "alert"

    def test_between_the_bounds_is_a_watch(self):
        detection = detectors.threshold_breach(7.0, watch_above=5.0, alert_above=10.0)
        assert detection is not None and detection.severity == "watch"

    def test_a_below_bound_fires_on_falling(self):
        detection = detectors.threshold_breach(85.0, watch_below=95.0, alert_below=90.0)
        assert detection is not None
        assert detection.severity == "alert" and detection.direction == "down"

    def test_a_healthy_value_is_silent(self):
        assert detectors.threshold_breach(3.0, watch_above=5.0, alert_above=10.0) is None

    def test_no_value_is_not_a_breach(self):
        """An empty query result is not a zero, and zero breaches every below-threshold."""
        assert detectors.threshold_breach(None, alert_below=90.0) is None

    def test_it_needs_no_history_at_all(self):
        """Which is why every risk scope carries thresholds: they are the only detector that
        works on the metrics Genesis has barely any history for."""
        assert detectors.threshold_breach(12.0, alert_above=10.0) is not None


class TestConcentration:
    def test_a_single_borrower_book_is_maximally_concentrated(self):
        detection = detectors.concentration([1000.0], watch_hhi=0.05, alert_hhi=0.15)
        assert detection is not None and detection.severity == "alert"

    def test_an_evenly_spread_book_is_silent(self):
        detection = detectors.concentration([100.0] * 100, watch_hhi=0.05, alert_hhi=0.15)
        assert detection is None

    def test_an_empty_book_produces_nothing(self):
        assert detectors.concentration([], watch_hhi=0.05, alert_hhi=0.15) is None
        assert detectors.concentration([None, 0.0], watch_hhi=0.05, alert_hhi=0.15) is None


class TestRankMovement:
    CURRENT = {"a": 10.0, "b": 9.0, "c": 8.0, "d": 7.0, "e": 6.0}

    def test_a_big_mover_is_reported_by_name(self):
        prior = {"a": 1.0, "b": 9.0, "c": 8.0, "d": 7.0, "e": 6.0}
        moves = dict(detectors.rank_movement(self.CURRENT, prior))
        assert "a" in moves
        assert moves["a"].direction == "up"

    def test_a_one_place_shuffle_is_not(self):
        """Branches swap by one or two between months for no reason anybody can act on."""
        prior = {"a": 9.5, "b": 10.0, "c": 8.0, "d": 7.0, "e": 6.0}
        assert detectors.rank_movement(self.CURRENT, prior) == []

    def test_a_member_missing_from_one_period_is_skipped(self):
        """An account that did not exist has no rank to have moved from, and treating it as
        last would report every new branch as a collapse."""
        prior = {"b": 9.0, "c": 8.0, "d": 7.0, "e": 6.0, "f": 1.0}
        moves = dict(detectors.rank_movement(self.CURRENT, prior))
        assert "a" not in moves and "f" not in moves

    def test_too_few_members_to_rank_produces_nothing(self):
        assert detectors.rank_movement({"a": 1.0}, {"a": 2.0}) == []


class TestStaleness:
    def test_a_fresh_table_is_silent(self):
        assert detectors.staleness(1, watch_days=2, alert_days=5) is None

    def test_a_stale_table_alerts(self):
        detection = detectors.staleness(9, watch_days=2, alert_days=5)
        assert detection is not None and detection.severity == "alert"

    def test_a_table_with_no_dated_rows_at_all_alerts(self):
        """Silence here is the worst case: every metric over the table is quietly about
        nothing, and nothing else in the product notices."""
        detection = detectors.staleness(None, watch_days=2, alert_days=5)
        assert detection is not None and detection.severity == "alert"


class TestTheCatalogHoldsUp:
    def test_every_scope_compiles(self, catalog):
        """A scope that cannot compile is a scan that silently finds nothing, which is
        indistinguishable on the dashboard from a book with no problems."""
        for scope in catalog.signals.scopes.values():
            compile_spec(scan._series_spec(scope, catalog), catalog, TODAY)

    def test_a_threshold_scope_declares_thresholds(self, catalog):
        for scope in catalog.signals.scopes.values():
            if "threshold" not in scope.detectors:
                continue
            assert any(
                (scope.watch_above, scope.alert_above, scope.watch_below, scope.alert_below)
            ), scope.id

    def test_a_structural_scope_has_a_dimension(self, catalog):
        for scope in catalog.signals.scopes.values():
            if {"concentration", "rank_movement"} & set(scope.detectors):
                assert scope.dimension, scope.id

    def test_a_concentration_scope_has_no_time_axis(self, catalog):
        """The prudential question is whether the book *is* concentrated, asked of the book
        as it stands — not whether it became more so."""
        for scope in catalog.signals.scopes.values():
            if "concentration" not in scope.detectors:
                continue
            assert catalog.signals.grain not in scan._series_spec(scope, catalog).dimensions

    def test_the_gaps_are_named(self, catalog):
        """A reader who does not know variance-to-plan is missing will read an empty feed
        as a clean book."""
        assert catalog.signals.unavailable
        for entry in catalog.signals.unavailable:
            assert entry.get("detector") and entry.get("needs")

    def test_every_data_health_check_names_a_real_table(self, catalog):
        for check in catalog.signals.data_health:
            assert check.table in catalog.tables
            assert check.watch_days <= check.alert_days


class TestSignalIdentity:
    def _signal(self, **kwargs):
        base = dict(scope="par30_by_branch", label="PAR 30", kind="threshold", text="x")
        base.update(kwargs)
        return Signal(**base)

    def test_the_same_problem_keeps_one_fingerprint(self):
        """A standing problem is one signal with a history. Without that, a director who
        acknowledged a breach on Monday sees it again on Tuesday and stops reading by
        Friday."""
        assert self._signal(member="Aluva").fingerprint == self._signal(member="Aluva").fingerprint

    def test_a_different_member_is_a_different_signal(self):
        assert self._signal(member="Aluva").fingerprint != self._signal(member="Kozhikode").fingerprint

    def test_a_different_detector_is_a_different_signal(self):
        """PAR breaching its limit and PAR jumping are two findings about one number, and
        collapsing them would hide whichever arrived second."""
        a = self._signal(member="Aluva", kind="threshold")
        b = self._signal(member="Aluva", kind="level_shift")
        assert a.fingerprint != b.fingerprint

    def test_the_reading_does_not_change_identity(self):
        """The problem has not become news again because the number moved a little."""
        a = self._signal(member="Aluva", value=11.0)
        b = self._signal(member="Aluva", value=13.0)
        assert a.fingerprint == b.fingerprint


class TestStore:
    @pytest.fixture(autouse=True)
    def _memory_only(self, monkeypatch):
        monkeypatch.setattr(store, "_ensure_table", lambda: False)
        store._MEMORY.clear()
        yield
        store._MEMORY.clear()

    def _signal(self, member="Aluva", severity="alert", **kwargs):
        return Signal(
            scope="par30_by_branch", label="PAR 30", kind="threshold",
            member=member, severity=severity, text="PAR 30 is above its limit.", **kwargs
        )

    def test_a_new_finding_is_new(self):
        assert store.record([self._signal()]) == 1

    def test_the_same_finding_twice_is_not(self):
        store.record([self._signal()])
        assert store.record([self._signal(value=12.0)]) == 0

    def test_a_re_scan_keeps_the_acknowledgement(self):
        """Acknowledging says "I have seen this", and a re-scan must not undo it."""
        signal = self._signal()
        store.record([signal])
        store.set_status(signal.fingerprint, "acknowledged", user="alice")
        store.record([self._signal(value=13.0)])
        assert store.open_signals()[0].status == "acknowledged"

    def test_an_acknowledged_signal_stays_in_the_feed(self):
        """Acknowledging is not fixing. A standing deterioration must not disappear by being
        read."""
        signal = self._signal()
        store.record([signal])
        store.set_status(signal.fingerprint, "acknowledged")
        assert len(store.open_signals()) == 1

    def test_a_resolved_signal_leaves_it(self):
        signal = self._signal()
        store.record([signal])
        store.set_status(signal.fingerprint, "resolved")
        assert store.open_signals() == []

    def test_alerts_come_before_watches(self):
        store.record([self._signal(member="A", severity="watch"),
                      self._signal(member="B", severity="alert")])
        assert [s.signal.member for s in store.open_signals()] == ["B", "A"]

    def test_an_invented_status_is_refused(self):
        signal = self._signal()
        store.record([signal])
        with pytest.raises(store.SignalStoreError):
            store.set_status(signal.fingerprint, "sorted")

    def test_an_unknown_signal_is_refused(self):
        with pytest.raises(store.SignalStoreError):
            store.set_status("nope", "acknowledged")

    def test_a_signal_seen_once_is_not_standing(self):
        store.record([self._signal()])
        assert not store.open_signals()[0].is_standing


class TestPersonas:
    """A persona reorders and preselects. It never changes what a number means."""

    def test_every_persona_leads_with_something(self, catalog):
        for persona in catalog.personas.values():
            assert persona.analyses, persona.id

    def test_every_reference_resolves(self, catalog):
        for persona in catalog.personas.values():
            for analysis_id in persona.analyses:
                assert analysis_id in catalog.analyses
            for scope_id in persona.signal_scopes:
                assert scope_id in catalog.signals.scopes
            for worklist_id in persona.worklists:
                assert worklist_id in catalog.worklists.presets

    def test_a_persona_declares_no_metrics_or_filters(self, catalog):
        """The restriction is the point: PAR 30 is PAR 30 at every desk. A persona that
        redefined one would give two people different answers with no way to discover why."""
        from dataclasses import fields

        names = {f.name for f in fields(next(iter(catalog.personas.values())))}
        assert not names & {"metrics", "filters", "thresholds", "watch_above"}

    def test_the_collections_desk_gets_a_list_to_work(self, catalog):
        assert "collections_today" in catalog.personas["collections"].worklists

    def test_an_unknown_persona_is_refused(self, catalog):
        with pytest.raises(morning.BriefingError):
            morning.build("nobody", catalog=catalog)


class TestBriefingHeadline:
    """Deterministic and never model-written, including when there is nothing to say."""

    def _signal(self, severity, label="PAR 30"):
        return Signal(scope="s", label=label, kind="threshold", severity=severity, text="x")

    def test_alerts_lead_and_are_counted(self):
        headline = morning._headline(
            [self._signal("alert"), self._signal("alert", "NPA ratio"), self._signal("watch")],
            [], "Chief Executive",
        )
        assert headline.startswith("2 things need attention")
        assert "PAR 30" in headline

    def test_an_acronym_survives_mid_sentence(self):
        headline = morning._headline([self._signal("alert", "NPA ratio")], [], "Finance")
        assert "npa" not in headline

    def test_watches_alone_say_nothing_is_urgent(self):
        headline = morning._headline([self._signal("watch")], [], "Risk")
        assert "Nothing urgent" in headline

    def test_no_signals_but_indicators_says_so(self):
        from app.services.nlq.contracts import AnalysisResult

        result = AnalysisResult(title="Portfolio health", compose="briefing")
        assert "No open signals" in morning._headline([], [result], "Risk")

    def test_nothing_at_all_does_not_claim_a_clean_book(self):
        """The single most dangerous sentence this product could print is "all clear" when
        the truth is that the scan has not run."""
        headline = morning._headline([], [], "Risk")
        assert "not the same as a clean book" in headline


class TestScanReporting:
    def test_abstention_is_reported_not_swallowed(self, catalog, monkeypatch):
        """"Not enough data yet" and "nothing is wrong" must never look the same."""
        monkeypatch.setattr(scan, "_scan_scope", lambda scope, cat, today: [])
        monkeypatch.setattr(scan, "_scan_data_health", lambda cat: ([], []))
        report = scan.run(catalog=catalog, today=TODAY)
        assert set(report.abstained) == set(catalog.signals.scopes)
        assert report.signals == []

    def test_one_broken_scope_does_not_lose_the_others(self, catalog, monkeypatch):
        from app.services.nlq.executor import ExecutionError

        def flaky(scope, cat, today):
            if scope.id == "par30_total":
                raise ExecutionError("boom")
            return [Signal(scope=scope.id, label=scope.label, kind="threshold", text="x")]

        monkeypatch.setattr(scan, "_scan_scope", flaky)
        monkeypatch.setattr(scan, "_scan_data_health", lambda cat: ([], []))
        report = scan.run(catalog=catalog, today=TODAY)
        assert report.scopes_failed == 1
        assert len(report.signals) == len(catalog.signals.scopes) - 1
        assert report.warnings

    def test_findings_are_ranked_before_they_are_returned(self, catalog, monkeypatch):
        def ranked(scope, cat, today):
            severity = "alert" if scope.id == "npa_total" else "watch"
            return [Signal(scope=scope.id, label=scope.label, kind="threshold",
                           severity=severity, text="x")]

        monkeypatch.setattr(scan, "_scan_scope", ranked)
        monkeypatch.setattr(scan, "_scan_data_health", lambda cat: ([], []))
        report = scan.run(catalog=catalog, today=TODAY)
        assert report.signals[0].scope == "npa_total"

    def test_every_signal_is_stamped_and_identified(self, catalog, monkeypatch):
        monkeypatch.setattr(
            scan, "_scan_scope",
            lambda scope, cat, today: [
                Signal(scope=scope.id, label=scope.label, kind="threshold", text="x")
            ],
        )
        monkeypatch.setattr(scan, "_scan_data_health", lambda cat: ([], []))
        report = scan.run(catalog=catalog, today=TODAY)
        for signal in report.signals:
            assert signal.detected_at is not None
            assert signal.id == signal.fingerprint


class TestSignalEvidence:
    """Every signal is one click from the chart behind it. A finding the reader cannot verify
    is a finding they have to take on faith, which is the thing this product does not ask."""

    def test_a_member_signal_filters_to_that_member(self, catalog):
        from app.services.nlq.contracts import Period, QuerySpec

        spec = QuerySpec(
            metrics=["par_30"], dimensions=["month", "branch"],
            period=Period(relative="last_12_months"),
        )
        filtered = scan._member_spec(spec, "branch", "1002", catalog)
        assert filtered.filters[-1].value == "1002"
        assert "branch" not in filtered.dimensions
        compile_spec(filtered, catalog, TODAY)

    def test_it_filters_on_the_raw_code_not_the_label(self, catalog):
        """The label is a display value; a filter carrying it would match nothing."""
        from app.services.nlq.contracts import Period, QuerySpec

        spec = QuerySpec(
            metrics=["par_30"], dimensions=["month", "branch"],
            period=Period(relative="last_12_months"),
        )
        assert scan._member_spec(spec, "branch", "1002", catalog).filters[-1].value != "Aluva"

    def test_a_data_health_signal_carries_no_spec(self, catalog, monkeypatch):
        """It is a finding about a table, not about a measure. Attaching a plausible-looking
        query would send the reader to a chart that cannot show them the problem."""
        class Result:
            rows = [{"newest": date(2020, 1, 1)}]

        monkeypatch.setattr("app.services.signals.scan.execute", lambda q: Result())
        found, _warnings = scan._scan_data_health(catalog)
        assert found
        assert all(signal.spec is None for signal in found)


class TestMemberLabels:
    """Scan rows come straight from the executor, not through the chart layer, so they carry
    raw codes and no `__raw` companion. Which half goes where matters: the code is what the
    evidence spec filters on, the label is what the sentence says."""

    def _rows(self):
        return [
            {"month": "2026-05-01", "branch": "1002", "par_30": 4.0},
            {"month": "2026-06-01", "branch": "1002", "par_30": 4.1},
            {"month": "2026-07-01", "branch": "1002", "par_30": 30.0},
        ]

    def test_the_signal_text_names_the_branch_not_its_code(self, catalog):
        scope = catalog.signals.scopes["par30_by_branch"]
        metric = catalog.metrics["par_30"]
        spec = scan._series_spec(scope, catalog)
        found = scan._scan_by_member(scope, metric, spec, self._rows(), catalog)
        assert found
        assert any("Aluva" in s.text for s in found)
        assert not any("1002" in s.text for s in found)

    def test_the_evidence_spec_filters_on_the_code(self, catalog):
        scope = catalog.signals.scopes["par30_by_branch"]
        metric = catalog.metrics["par_30"]
        spec = scan._series_spec(scope, catalog)
        found = scan._scan_by_member(scope, metric, spec, self._rows(), catalog)
        branch_filters = [
            f for s in found if s.spec for f in s.spec.filters if f.field == "branch"
        ]
        assert branch_filters
        assert all(f.value == "1002" for f in branch_filters)

    def test_an_undecodable_member_shows_its_code_rather_than_an_invented_name(self, catalog):
        assert scan._label_for("branch", "9999", catalog) == "Branch 9999"
        assert scan._label_for("borrower", "ACME LTD", catalog) == "ACME LTD"
