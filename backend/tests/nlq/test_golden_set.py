"""The golden question set: structure now, planner accuracy in Phase 2.

The set is written before the planner exists, so at this stage it validates itself — every
answerable case must compile, and against a live warehouse must actually execute. That
makes it a specification the planner can then be scored against, rather than a wish list
written after the fact and bent to whatever the model happened to do.
"""

from pathlib import Path

import pytest
import yaml

from app.services.nlq.compiler import CompileError, bind, compile_spec
from app.services.nlq.contracts import QuerySpec
from tests.nlq.conftest import requires_db

GOLDEN_PATH = Path(__file__).parent / "golden" / "questions.yaml"
VALID_ROUTES = {"queryspec", "sql", "clarify", "refuse"}
VALID_REASONS = {"out_of_scope", "not_in_data", "predictive", "advice", "unsafe"}


def load_cases() -> list[dict]:
    return yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))


CASES = load_cases()
ANSWERABLE = [c for c in CASES if c["route"] == "queryspec"]


def case_id(case: dict) -> str:
    return f"{case['id']}-{case['category']}"


class TestSetStructure:
    def test_ids_are_unique(self):
        ids = [c["id"] for c in CASES]
        assert len(set(ids)) == len(ids)

    def test_every_case_has_a_question_and_a_valid_route(self):
        for case in CASES:
            assert case.get("question"), case["id"]
            assert case["route"] in VALID_ROUTES, case["id"]

    def test_answerable_cases_carry_a_spec(self):
        for case in ANSWERABLE:
            assert case.get("spec"), f"{case['id']} is routed to queryspec but has no spec"

    def test_non_answerable_cases_carry_no_spec(self):
        """A refusal with a spec attached invites someone to "just run it anyway"."""
        for case in CASES:
            if case["route"] in ("refuse", "clarify"):
                assert "spec" not in case, case["id"]

    def test_refusals_declare_a_reason(self):
        for case in CASES:
            if case["route"] == "refuse":
                assert case.get("reason") in VALID_REASONS, case["id"]

    def test_the_set_covers_every_category_that_matters(self):
        categories = {c["category"] for c in CASES}
        for required in (
            "aggregate", "breakdown", "trend", "ranking", "ratio", "point_in_time",
            "comparison", "enum_decode", "coverage", "refuse", "clarify",
        ):
            assert required in categories, f"golden set has no {required} case"

    def test_negative_cases_are_a_meaningful_share_of_the_set(self):
        """Refusing well is a feature. A set that is all happy paths trains a planner that
        answers everything, which is the failure this project most needs to avoid."""
        negative = [c for c in CASES if c["route"] in ("refuse", "clarify")]
        assert len(negative) >= 10
        assert len(negative) / len(CASES) >= 0.15


class TestAnswerableCasesCompile:
    @pytest.mark.parametrize("case", ANSWERABLE, ids=case_id)
    def test_spec_is_valid_and_compiles(self, case):
        spec = QuerySpec.model_validate(case["spec"])
        compiled = compile_spec(spec)
        assert compiled.sql.startswith("SELECT")
        assert "LIMIT" in compiled.sql

    @pytest.mark.parametrize("case", ANSWERABLE, ids=case_id)
    def test_no_user_value_is_interpolated_into_the_sql(self, case):
        compiled = compile_spec(QuerySpec.model_validate(case["spec"]))
        for key, value in compiled.params.items():
            if isinstance(value, str) and len(value) > 3:
                assert value not in compiled.sql, f"{key} was interpolated, not bound"

    def test_coverage_cases_carry_the_expected_warning(self):
        for case in CASES:
            if "expect_warning" not in case:
                continue
            compiled = compile_spec(QuerySpec.model_validate(case["spec"]))
            joined = " ".join(compiled.warnings)
            assert case["expect_warning"] in joined, (
                f"{case['id']} should warn about: {case['expect_warning']}"
            )


class TestRefusedCasesAreNotSecretlyAnswerable:
    def test_gl_by_product_cannot_be_compiled(self):
        """g104. If a future catalog edit ever made this compile, the refusal would be
        wrong and this test says so."""
        with pytest.raises(CompileError):
            compile_spec(
                QuerySpec.model_validate(
                    {
                        "metrics": ["gl_balance"],
                        "dimensions": ["product"],
                        "period": {"relative": "this_fy"},
                    }
                )
            )

    def test_monthly_gl_uses_the_governed_daily_balance_view(self):
        compiled = compile_spec(
            QuerySpec.model_validate(
                {
                    "metrics": ["gl_balance"],
                    "dimensions": ["month"],
                    "period": {"relative": "last_fy"},
                }
            )
        )
        assert "gold.gl_daily_balances" in compiled.sql
        assert "generate_series" in compiled.sql
        assert "bucket_start" in compiled.sql


@requires_db
class TestAnswerableCasesExecute:
    """Compiling is not enough — the SQL must be accepted by Postgres."""

    @pytest.mark.parametrize("case", ANSWERABLE, ids=case_id)
    def test_query_runs(self, case, warehouse_cursor):
        compiled = compile_spec(QuerySpec.model_validate(case["spec"]))
        sql, params = bind(compiled.sql, compiled.params)
        warehouse_cursor.execute(sql, params)
        warehouse_cursor.fetchall()  # must not raise
