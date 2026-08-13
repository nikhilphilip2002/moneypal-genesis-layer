"""Catalog structure tests — no database required.

The catalog is the product; a silent regression here degrades every answer downstream.
"""

import pytest
import yaml

from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.loader import ACTIVE_DEFS_DIR, DEFS_DIR


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


class TestLoads:
    def test_catalog_loads_and_validates(self, catalog):
        assert catalog.metrics and catalog.dimensions and catalog.tables

    def test_version_is_content_addressed(self, catalog):
        assert len(catalog.version) == 12
        assert get_catalog().version == catalog.version

    def test_every_yaml_file_is_a_list(self):
        for path in (*DEFS_DIR.glob("*.yaml"), *ACTIVE_DEFS_DIR.glob("*.yaml")):
            assert isinstance(yaml.safe_load(path.read_text()), list), path.name

    def test_joins_yaml_avoids_the_yaml_boolean_trap(self):
        """A bare `on:` key parses as the boolean True under YAML 1.1, which would silently
        drop every join condition and turn joins into cross products."""
        raw = yaml.safe_load((ACTIVE_DEFS_DIR / "joins.yaml").read_text())
        for entry in raw:
            assert "on_columns" in entry, f"{entry.get('id')} lost its join condition"
            assert True not in entry, f"{entry.get('id')} has a YAML-boolean key"


class TestReferentialIntegrity:
    def test_metric_base_tables_exist(self, catalog):
        for metric in catalog.metrics.values():
            assert metric.base_table in catalog.allowed_tables(), metric.id

    def test_active_allowlist_contains_only_gold_views(self, catalog):
        assert catalog.allowed_tables()
        assert all(table.startswith("gold.") for table in catalog.allowed_tables())

    def test_dimension_tables_exist(self, catalog):
        for dim in catalog.dimensions.values():
            if not dim.is_time:
                assert dim.table in catalog.allowed_tables(), dim.id

    def test_decodes_resolve_to_enum_blocks(self, catalog):
        for dim in catalog.dimensions.values():
            if dim.decode:
                assert dim.decode in catalog.enums, dim.id

    def test_join_endpoints_exist(self, catalog):
        for join in catalog.joins:
            assert join.left in catalog.allowed_tables(), join.id
            assert join.right in catalog.allowed_tables(), join.id

    def test_no_duplicate_join_paths(self, catalog):
        """Rule 3 of §2.5: an ambiguous path must be impossible, not merely unlikely."""
        seen = set()
        for join in catalog.joins:
            pair = frozenset((join.left, join.right))
            assert pair not in seen, f"two declared paths between {tuple(pair)}"
            seen.add(pair)


class TestGrainDiscipline:
    """The field that prevents the most dangerous class of wrong answer."""

    def test_point_in_time_metrics_can_be_pinned(self, catalog):
        for metric in catalog.metrics.values():
            if metric.grain == "point_in_time":
                assert (
                    metric.as_of_column
                    or metric.as_of_function
                    or metric.no_time_travel
                    or metric.year_column
                ), (
                    f"{metric.id} is point_in_time but cannot be pinned to a date — it "
                    "would be silently averaged"
                )

    def test_as_of_metrics_declare_a_collapse_key(self, catalog):
        for metric in catalog.metrics.values():
            if metric.as_of_column and not metric.as_of_function:
                assert metric.as_of_key, (
                    f"{metric.id} reads an event log but declares no key to collapse it by"
                )

    def test_ratio_metrics_have_both_halves(self, catalog):
        for metric in catalog.metrics.values():
            if metric.is_ratio:
                assert metric.numerator and metric.denominator, metric.id

    def test_ratios_survive_an_empty_numerator(self, catalog):
        """PAR 90 is genuinely zero in this data. It must render 0%, not "no data" —
        COALESCE on the numerator is what makes that true."""
        sql = catalog.metrics["par_90"].sql("t")
        assert "COALESCE(" in sql
        assert "NULLIF(" in sql

    def test_portfolio_metrics_use_the_reviewed_as_of_function(self, catalog):
        metric = catalog.metrics["par_30"]
        assert metric.as_of_function == "gold.portfolio_snapshot_as_of"
        assert metric.point_in_time


class TestSafetyMetadata:
    def test_pii_columns_are_tagged(self, catalog):
        pii = {c.id for c in catalog.columns.values() if c.is_pii}
        for expected in ("customer.full_name", "customer.dob", "loan.customer_name"):
            assert expected in pii

    def test_gold_joins_do_not_fan_out_reviewed_metrics(self, catalog):
        assert all(not join.fans_out for join in catalog.joins)

    def test_gl_is_isolated_from_the_loan_book(self, catalog):
        """No join path — a GL-by-product question must be refusable, not answerable."""
        assert catalog.join_between(
            "gold.gl_daily_balances", "gold.loan_account_master"
        ) is None

    def test_unratified_metrics_are_flagged(self, catalog):
        """PAR's denominator is the classified subset, not the whole book. Until the client
        confirms which their board pack uses, every PAR answer carries the badge."""
        assert catalog.metrics["par_30"].requires_signoff
        assert catalog.metrics["par_30"].signoff_note.strip()


class TestEnums:
    def test_product_synonyms_resolve(self, catalog):
        product = catalog.enums["product"]
        for phrase in ("gold loans", "MSME", "microfinance", "JLG"):
            assert product.code_for(phrase) is not None, phrase

    def test_labels_round_trip(self, catalog):
        product = catalog.enums["product"]
        assert product.label_for(1) == "Gold Loans"
        assert product.label_for("16") == "Business & MSME Loans"

    def test_unknown_code_falls_back_to_the_bare_code(self, catalog):
        """An invented category name cannot be spotted as wrong; a bare code can."""
        assert catalog.enums["scheme"].label_for("1328") == "Scheme #1328"

    def test_no_fuzzy_matching(self, catalog):
        """A near-miss must not silently answer about a different product."""
        assert catalog.enums["product"].code_for("gld") is None
        assert catalog.enums["product"].code_for("loans") is None


class TestSearch:
    @pytest.mark.parametrize(
        "question,expected",
        [
            ("what is our PAR 30", "par_30"),
            ("show me collection efficiency", "collection_efficiency"),
            ("how much did we disburse", "disbursement_total"),
        ],
    )
    def test_acronyms_and_phrases_match_lexically(self, catalog, question, expected):
        """Short acronyms embed poorly; lexical matching is what makes PAR findable."""
        assert expected in {m.id for m in catalog.search_metrics(question)}
