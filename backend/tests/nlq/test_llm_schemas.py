"""The response_format schemas, checked as the contract they actually are.

Under constrained decoding the schema is not documentation — it is the grammar. Anything
it permits, a model will eventually emit, and a permitted-but-useless shape surfaces to
the user as an unexplained refusal rather than as a validation error.
"""

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm.schemas import plan_schema

ROUTES = ("queryspec", "sql", "clarify", "refuse")


@pytest.fixture(scope="module")
def schema():
    return plan_schema(get_catalog())


def _branch(schema, route):
    for option in schema["anyOf"]:
        if option["properties"]["route"]["const"] == route:
            return option
    raise AssertionError(f"no branch for route {route!r}")


class TestPlanSchemaIsTagged:
    """A flat object with `required: ["route"]` lets the grammar close after the tag.

    That is what produced the outage: the model emitted {"route":"queryspec",
    "confidence":0.98,"reasoning":"..."} with no spec — legal under the old schema — so the
    planner rejected it twice, demoted to text-to-SQL, and the user was told the loan book
    could not answer the question.
    """

    def test_every_route_has_exactly_one_branch(self, schema):
        routes = [opt["properties"]["route"]["const"] for opt in schema["anyOf"]]
        assert sorted(routes) == sorted(ROUTES)

    @pytest.mark.parametrize(
        "route,field",
        [("queryspec", "spec"), ("sql", "intent"), ("clarify", "question"), ("refuse", "reason")],
    )
    def test_each_branch_requires_its_payload(self, schema, route, field):
        assert field in _branch(schema, route)["required"]

    @pytest.mark.parametrize("route", ROUTES)
    def test_no_branch_accepts_another_routes_fields(self, schema, route):
        """`additionalProperties: false` per branch is what keeps the tag meaningful."""
        branch = _branch(schema, route)
        assert branch["additionalProperties"] is False
        foreign = {"spec", "intent", "question", "reason"} - set(branch["properties"])
        assert foreign, f"{route} branch declares every payload field"

    def test_spec_precedes_the_commentary(self, schema):
        """Constrained decoding emits properties in order; if the budget runs out it must
        be the prose that is lost, never the spec."""
        keys = list(_branch(schema, "queryspec")["properties"])
        assert keys.index("spec") < keys.index("reasoning")

    def test_reasoning_is_capped(self, schema):
        """An uncapped free-text field on a thinking model eats the whole token budget."""
        assert _branch(schema, "queryspec")["properties"]["reasoning"]["maxLength"] <= 300

    def test_metric_enum_comes_from_the_catalog(self, schema):
        metrics = _branch(schema, "queryspec")["properties"]["spec"]["properties"]["metrics"]
        assert set(metrics["items"]["enum"]) == set(get_catalog().metrics)
