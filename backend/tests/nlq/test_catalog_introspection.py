"""Assert the catalog still describes the database it claims to describe.

Build plan item 8. Nothing in Postgres
enforces this: without these tests a renamed column in the next ingestion would surface as
a broken answer in front of a user, not as a red build.
"""

import pytest

from app.services.nlq.catalog import get_catalog
from tests.nlq.conftest import requires_db

pytestmark = requires_db


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


@pytest.fixture(scope="module")
def live_columns(warehouse_cursor):
    warehouse_cursor.execute(
        "SELECT table_schema || '.' || table_name, column_name "
        "FROM information_schema.columns WHERE table_schema = 'gold'"
    )
    mapping: dict[str, set[str]] = {}
    for table, column in warehouse_cursor.fetchall():
        mapping.setdefault(table, set()).add(column)
    return mapping


class TestTablesExist:
    def test_every_catalog_table_exists(self, catalog, live_columns):
        missing = [t for t in catalog.allowed_tables() if t not in live_columns]
        assert not missing, f"catalog references tables that do not exist: {missing}"

    def test_no_catalog_table_is_outside_gold(self, catalog):
        """Only governed Gold views may enter the LLM SQL allowlist."""
        for table in catalog.allowed_tables():
            assert table.startswith("gold."), table


class TestColumnsExist:
    def test_curated_columns_exist(self, catalog, live_columns):
        missing = [
            f"{c.table}.{c.column}"
            for c in catalog.columns.values()
            if c.column not in live_columns.get(c.table, set())
        ]
        assert not missing, f"columns.yaml references missing columns: {missing}"

    def test_dimension_columns_exist(self, catalog, live_columns):
        missing = [
            f"{d.table}.{d.column}"
            for d in catalog.dimensions.values()
            if not d.is_time and d.column not in live_columns.get(d.table, set())
        ]
        assert not missing, f"dimensions.yaml references missing columns: {missing}"

    def test_join_columns_exist(self, catalog, live_columns):
        missing = []
        for join in catalog.joins:
            for left_col, right_col in join.on:
                if left_col not in live_columns.get(join.left, set()):
                    missing.append(f"{join.id}: {join.left}.{left_col}")
                if right_col not in live_columns.get(join.right, set()):
                    missing.append(f"{join.id}: {join.right}.{right_col}")
        assert not missing, f"joins.yaml references missing columns: {missing}"

    def test_metric_expressions_reference_real_columns(self, catalog, live_columns):
        """Parses the identifiers out of each metric's SQL and checks them against the
        warehouse — the check that would have caught `glbbal_bal_date`, a column that
        sounds obvious and does not exist."""
        import re

        problems = []
        for metric in catalog.metrics.values():
            available = live_columns.get(metric.base_table, set())
            expression = metric.sql("{t}")
            for candidate in re.findall(r"\{t\}\.(\w+)", expression):
                if candidate not in available:
                    problems.append(f"{metric.id}: {metric.base_table}.{candidate}")
            for column in (metric.date_column, metric.as_of_column, metric.year_column):
                if column and column not in available:
                    problems.append(f"{metric.id}: {metric.base_table}.{column}")
            for key in metric.as_of_key:
                if key not in available:
                    problems.append(f"{metric.id}: as_of_key {metric.base_table}.{key}")
        assert not problems, f"metrics.yaml references missing columns: {problems}"


class TestDocumentedFactsStillHold:
    """The catalog states figures as fact. If the warehouse moves, they become lies."""

    def test_row_counts_are_current(self, catalog, warehouse_cursor):
        drifted = []
        for table in catalog.tables.values():
            if table.row_count is None:
                continue
            warehouse_cursor.execute(f"SELECT count(*) FROM {table.table}")
            actual = warehouse_cursor.fetchone()[0]
            if actual != table.row_count:
                drifted.append(f"{table.id}: catalog says {table.row_count}, found {actual}")
        assert not drifted, "row counts in tables.yaml are stale: " + "; ".join(drifted)

    def test_portfolio_as_of_function_is_available(self, warehouse_cursor):
        warehouse_cursor.execute(
            "SELECT count(*) FROM gold.portfolio_snapshot_as_of(CURRENT_DATE)"
        )
        assert warehouse_cursor.fetchone()[0] > 0

    def test_enum_codes_are_all_present_in_the_data(self, catalog, warehouse_cursor):
        """A code documented but absent is fine (NPA is). A code in the data but missing
        from the enum renders as a bare number in a chart, which is what this catches."""
        warehouse_cursor.execute(
            "SELECT DISTINCT product_code FROM gold.loan_account_master"
        )
        live = {str(r[0]) for r in warehouse_cursor.fetchall()}
        documented = set(catalog.enums["product"].values)
        assert not (live - documented), f"undocumented product codes in use: {live - documented}"

    def test_branch_codes_are_all_documented(self, catalog, warehouse_cursor):
        warehouse_cursor.execute(
            "SELECT DISTINCT branch_code FROM gold.loan_account_master"
        )
        live = {str(r[0]) for r in warehouse_cursor.fetchall()}
        documented = set(catalog.enums["branch"].values)
        assert not (live - documented), f"undocumented branch codes in use: {live - documented}"
