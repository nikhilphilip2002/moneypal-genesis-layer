"""Worklists: the rules, the ranking, and the reason on every row.

The scoring and the reason rendering are pure, so "why is this account third?" is a test
rather than an argument. The SQL assembly runs against the real catalog with no database —
compiling is enough to prove the rules reference columns that exist and stay inside the
reviewed relation.
"""

from datetime import date

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.loader import ScoreComponent, ScoreModel
from app.services.nlq.compiler import bind
from app.services.nlq.contracts import Filter
from app.services.worklists import runner as build_module
from app.services.worklists import rules as rule_engine
from app.services.worklists import store
from app.services.worklists.score import NEUTRAL, prioritise

AS_OF = date(2026, 7, 31)


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def _sql(preset="collections_today", **kwargs):
    compiled, rules = rule_engine.compile_worklist(preset, as_of=AS_OF, **kwargs)
    sql, params = bind(compiled.sql, compiled.params)
    return sql, params, rules


class TestTheCatalogHoldsUp:
    def test_every_preset_compiles(self, catalog):
        for preset_id in catalog.worklists.presets:
            rule_engine.compile_worklist(preset_id, catalog=catalog, as_of=AS_OF)

    def test_every_rule_belongs_to_at_least_one_preset(self, catalog):
        """An unreferenced rule is a rule nobody reviewed against a real list."""
        used = {r for preset in catalog.worklists.presets.values() for r in preset.rules}
        assert set(catalog.worklists.rules) == used

    def test_every_rule_states_a_reason(self, catalog):
        """A row with no reason gets skipped by the officer, which makes the whole list
        advisory rather than a queue of work."""
        for rule in catalog.worklists.rules.values():
            assert rule.reason.strip(), rule.id

    def test_the_score_weights_sum_to_one(self, catalog):
        total = sum(c.weight for c in catalog.worklists.score.components)
        assert total == pytest.approx(1.0)

    def test_the_last_playbook_catches_everything(self, catalog):
        """Otherwise an account can reach a worklist with no recommended action at all."""
        assert catalog.worklists.playbook_for("STD", 0) is not None
        assert catalog.worklists.playbook_for(None, None) is not None

    def test_the_gaps_are_named(self, catalog):
        """The rules we cannot write are declared next to the ones we can, so a reader knows
        the shape of what is missing rather than assuming the list is complete."""
        assert catalog.worklists.unavailable
        for entry in catalog.worklists.unavailable:
            assert entry.get("rule") and entry.get("needs")


class TestGeneratedSql:
    def test_it_selects_one_boolean_per_rule(self, catalog):
        sql, _params, rules = _sql()
        for rule in rules:
            assert f"AS {rule_engine.RULE_PREFIX}{rule.id}" in sql

    def test_it_only_returns_accounts_that_triggered_something(self):
        """Without the OR of the predicates in the WHERE clause a worklist is the book."""
        sql, _params, rules = _sql()
        assert "WHERE" in sql
        where = sql.split("WHERE", 1)[1]
        assert " OR " in where

    def test_it_reads_only_the_reviewed_relation(self, catalog):
        sql, _params, _rules = _sql()
        tables = {"gold.portfolio_daily_snapshot", "gold.loan_account_master"}
        for token in ("gold.", "bronze.", "silver.", "public."):
            for fragment in sql.split(token)[1:]:
                name = token + fragment.split()[0].strip("(),")
                assert name in tables, name

    def test_values_are_bound_not_interpolated(self, catalog):
        sql, params, _rules = _sql(filters=[Filter(field="branch", op="eq", value="1002")])
        assert "1002" not in sql
        assert "1002" in [str(p) for p in params]

    def test_a_filter_the_list_cannot_honour_is_refused(self, catalog):
        """Silently dropping it would send one branch's accounts to another branch's team."""
        with pytest.raises(rule_engine.RuleError):
            _sql(filters=[Filter(field="dpd_bucket", op="eq", value="90+")])

    def test_an_unsupported_operator_is_refused(self, catalog):
        with pytest.raises(rule_engine.RuleError):
            _sql(filters=[Filter(field="branch", op="contains", value="Alu")])

    def test_an_unknown_preset_is_refused(self, catalog):
        with pytest.raises(rule_engine.RuleError):
            rule_engine.compile_worklist("no_such_list", catalog=catalog, as_of=AS_OF)

    def test_the_limit_is_capped(self, catalog):
        _sql_text, params, _rules = _sql(limit=5000)
        assert 200 in params


class TestPriorityScore:
    MODEL = ScoreModel(
        method="percentile_rank",
        components=(
            ScoreComponent(id="overdue", label="Overdue", weight=0.6),
            ScoreComponent(id="dpd", label="DPD", weight=0.4),
        ),
    )

    def test_the_worst_row_on_both_axes_scores_one(self):
        rows = [{"overdue": 100, "dpd": 90}, {"overdue": 1, "dpd": 1}]
        scores = [s for s, _ in prioritise(rows, self.MODEL)]
        assert scores[0] == pytest.approx(1.0)
        assert scores[1] == pytest.approx(0.0)

    def test_one_huge_account_does_not_flatten_the_rest(self):
        """Min-max normalisation would compress the other four to nearly zero on overdue and
        sort the list by exposure alone, which is not what a collections day looks like."""
        rows = [
            {"overdue": 50_000_000, "dpd": 5},
            {"overdue": 400, "dpd": 200},
            {"overdue": 300, "dpd": 150},
            {"overdue": 200, "dpd": 100},
            {"overdue": 100, "dpd": 50},
        ]
        scores = [s for s, _ in prioritise(rows, self.MODEL)]
        assert scores[1] > scores[0]

    def test_a_missing_value_is_not_a_zero(self):
        """An account with no recorded last payment has an unknown days-since-payment, not a
        payment today. It sits in the middle rather than at the bottom."""
        rows = [{"overdue": 100, "dpd": 90}, {"overdue": 50, "dpd": None}, {"overdue": 1, "dpd": 1}]
        _score, weights = prioritise(rows, self.MODEL)[1]
        dpd = next(w for w in weights if w.id == "dpd")
        assert dpd.value == pytest.approx(NEUTRAL)

    def test_ties_share_a_rank(self):
        """Two accounts with identical arrears must not be separated by the order the
        database happened to return them in."""
        rows = [{"overdue": 100, "dpd": 10}, {"overdue": 100, "dpd": 10}]
        scores = [s for s, _ in prioritise(rows, self.MODEL)]
        assert scores[0] == scores[1]

    def test_the_terms_add_up_to_the_score(self):
        rows = [{"overdue": 100, "dpd": 90}, {"overdue": 1, "dpd": 1}]
        for score, weights in prioritise(rows, self.MODEL):
            assert sum(w.contribution for w in weights) == pytest.approx(score, abs=1e-3)

    def test_every_weight_is_reported(self):
        rows = [{"overdue": 100, "dpd": 90}]
        _score, weights = prioritise(rows, self.MODEL)[0]
        assert {w.id for w in weights} == {"overdue", "dpd"}
        assert all(w.weight for w in weights)

    def test_an_empty_list_scores_nothing(self):
        assert prioritise([], self.MODEL) == []


class TestReasons:
    def test_a_reason_carries_this_row_s_numbers(self, catalog):
        rule = catalog.worklists.rules["payments_stalled"]
        row = {"days_since_last_payment": 184, "total_overdue": 240000.0}
        text = build_module._reason(rule, row, catalog)
        assert "184" in text
        assert "{" not in text

    def test_numbers_are_formatted_the_way_the_product_formats_them(self, catalog):
        """A reason a person has to decode is a reason they skip."""
        rule = catalog.worklists.rules["payments_stalled"]
        row = {"days_since_last_payment": 184, "total_overdue": 240000.0}
        assert "240000.0" not in build_module._reason(rule, row, catalog)

    def test_a_missing_value_says_so_rather_than_printing_none(self, catalog):
        rule = catalog.worklists.rules["payments_stalled"]
        text = build_module._reason(rule, {"days_since_last_payment": None}, catalog)
        assert "None" not in text
        assert "not recorded" in text

    def test_every_rule_renders_without_leaving_a_placeholder(self, catalog):
        """A reason template naming a column that is not selected renders to the reader as a
        literal brace, which the catalog validator rejects — this pins the behaviour too."""
        row = {c.id: 1 for c in catalog.worklists.columns}
        for rule in catalog.worklists.rules.values():
            assert "{" not in build_module._reason(rule, row, catalog)


class TestRanking:
    """`_rank` is pure over decoded rows, so the whole ordering policy is testable with no
    database."""

    def _rows(self, catalog):
        return [
            {
                "loan_account_number": "A1", "dpd_days": 5, "total_overdue": 100.0,
                "principal_outstanding": 1000.0, "days_since_last_payment": 5,
                "asset_class": "Standard", "asset_class__raw": "STD",
                f"{rule_engine.RULE_PREFIX}early_stress": True,
            },
            {
                "loan_account_number": "A2", "dpd_days": 200, "total_overdue": 50.0,
                "principal_outstanding": 500.0, "days_since_last_payment": 200,
                "asset_class": "NPA", "asset_class__raw": "NPA",
                f"{rule_engine.RULE_PREFIX}payments_stalled": True,
            },
        ]

    def _ranked(self, catalog):
        rules = tuple(catalog.worklists.rules[r] for r in ("payments_stalled", "early_stress"))
        return build_module._rank(self._rows(catalog), rules, catalog)

    def test_an_alert_outranks_a_watch_whatever_the_score(self, catalog):
        """The score orders accounts within a class of problem; it does not compare classes.
        A stalled account scoring 0.4 still needs a call before a 1-day-late one scoring 0.9."""
        items = self._ranked(catalog)
        assert items[0].account == "A2"
        assert items[0].severity == "alert"

    def test_ranks_are_contiguous_and_match_the_order(self, catalog):
        items = self._ranked(catalog)
        assert [i.rank for i in items] == list(range(1, len(items) + 1))

    def test_the_playbook_is_matched_on_the_raw_code(self, catalog):
        """Matching on the decoded label would silently miss every account: the playbook says
        NPA, the row says "NPA" only after decoding, and the codes are what policy names."""
        npa = next(i for i in self._ranked(catalog) if i.account == "A2")
        assert "recovery" in npa.action.lower()
        assert npa.owner

    def test_a_row_that_triggered_nothing_is_dropped(self, catalog):
        rules = tuple(catalog.worklists.rules[r] for r in ("payments_stalled",))
        rows = [{"loan_account_number": "A9", "dpd_days": 0, "total_overdue": 0.0}]
        assert build_module._rank(rows, rules, catalog) == []

    def test_the_row_fields_exclude_the_rule_booleans(self, catalog):
        item = self._ranked(catalog)[0]
        assert not any(k.startswith(rule_engine.RULE_PREFIX) for k in item.fields)
        assert not any(k.endswith("__raw") for k in item.fields)


class TestExport:
    def test_the_csv_carries_the_reason_and_the_action(self, catalog):
        """A CSV of account numbers with no reason is a list somebody has to re-derive
        before they can use it, which means they will not."""
        from app.services.nlq.contracts import Lineage, Worklist

        rules = tuple(catalog.worklists.rules[r] for r in ("payments_stalled", "early_stress"))
        items = build_module._rank(TestRanking()._rows(catalog), rules, catalog)
        worklist = Worklist(
            id="collections_today", title="Today's list",
            columns=build_module._columns(catalog), items=items,
            lineage=Lineage(path="queryspec", sql="SELECT 1"),
        )
        csv_text = build_module.to_csv(worklist)
        assert "reasons" in csv_text.splitlines()[0]
        assert "action" in csv_text.splitlines()[0]
        assert "A2" in csv_text


class TestSavedLists:
    @pytest.fixture(autouse=True)
    def _memory_only(self, monkeypatch):
        monkeypatch.setattr(store, "_ensure_table", lambda: False)
        store._MEMORY.clear()
        yield
        store._MEMORY.clear()

    def _worklist(self, catalog):
        from app.services.nlq.contracts import Lineage, Worklist

        rules = tuple(catalog.worklists.rules[r] for r in ("payments_stalled", "early_stress"))
        return Worklist(
            id="collections_today", title="Today's list",
            columns=build_module._columns(catalog),
            items=build_module._rank(TestRanking()._rows(catalog), rules, catalog),
            lineage=Lineage(path="queryspec", sql="SELECT 1"),
        )

    def test_saving_freezes_the_rows(self, catalog):
        """Re-running the rules tomorrow is the next list, not this one — an account paid
        overnight would otherwise vanish along with the note saying who called it."""
        saved = store.save(self._worklist(catalog), owner="alice")
        fetched = store.get(saved.worklist_id, owner="alice")
        assert fetched is not None
        assert [i.account for i in fetched.worklist.items] == ["A2", "A1"]

    def test_every_account_starts_open(self, catalog):
        saved = store.save(self._worklist(catalog), owner="alice")
        assert set(saved.statuses) == {"A1", "A2"}
        assert all(v["status"] == "open" for v in saved.statuses.values())

    def test_a_status_is_recorded_with_who_and_what(self, catalog):
        saved = store.save(self._worklist(catalog), owner="alice")
        updated = store.set_status(
            saved.worklist_id, "A2", "promised", owner="alice",
            note="pays Friday", assigned_to="ravi",
        )
        assert updated.statuses["A2"]["status"] == "promised"
        assert updated.statuses["A2"]["note"] == "pays Friday"
        assert updated.statuses["A2"]["assigned_to"] == "ravi"

    def test_an_invented_status_is_refused(self, catalog):
        saved = store.save(self._worklist(catalog), owner="alice")
        with pytest.raises(store.WorklistStoreError):
            store.set_status(saved.worklist_id, "A2", "sorted", owner="alice")

    def test_an_account_not_on_the_list_is_refused(self, catalog):
        saved = store.save(self._worklist(catalog), owner="alice")
        with pytest.raises(store.WorklistStoreError):
            store.set_status(saved.worklist_id, "A99", "contacted", owner="alice")

    def test_lists_are_isolated_by_owner(self, catalog):
        saved = store.save(self._worklist(catalog), owner="alice")
        assert store.get(saved.worklist_id, owner="bob") is None
        assert not store.list_recent(owner="bob")

    def test_the_listing_counts_what_is_left_to_do(self, catalog):
        saved = store.save(self._worklist(catalog), owner="alice")
        store.set_status(saved.worklist_id, "A2", "paid", owner="alice")
        summary = store.list_recent(owner="alice")[0]
        assert summary.item_count == 2
        assert summary.open_count == 1


class TestAccountNumbersAreIdentifiers:
    """Postgres hands `loan_account_number` back as `numeric`, so it arrives as a float and
    rendered as "1000400003373.0" on a live list. An officer reading that off a screen to key
    into the core system has to know to drop the ".0" — exactly the friction that gets a list
    abandoned."""

    def _item(self, catalog, account):
        rules = tuple(catalog.worklists.rules[r] for r in ("early_stress",))
        rows = [{
            "loan_account_number": account, "dpd_days": 5, "total_overdue": 100.0,
            "principal_outstanding": 1000.0,
            f"{rule_engine.RULE_PREFIX}early_stress": True,
        }]
        return build_module._rank(rows, rules, catalog)[0]

    def test_a_numeric_account_loses_its_decimal_tail(self, catalog):
        assert self._item(catalog, 1000400003373.0).account == "1000400003373"

    def test_the_row_the_csv_exports_matches(self, catalog):
        item = self._item(catalog, 1000400003373.0)
        assert item.fields["loan_account_number"] == "1000400003373"

    def test_a_text_account_number_is_untouched(self, catalog):
        """Not every core system uses numeric keys, and stripping a leading zero from an
        opaque identifier would produce an account that does not exist."""
        assert self._item(catalog, "0042-A").account == "0042-A"
