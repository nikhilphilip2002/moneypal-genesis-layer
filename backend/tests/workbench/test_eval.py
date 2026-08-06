"""The routing eval: does the router send each question to the right source(s)?

Two things are tested here. The harness itself — the scorer must count correct routes and
surface the failures — is tested with a deterministic fake router, so it needs no model. The
golden file is validated for shape. The real run against the live model is a separate,
opt-in path (test_routing_accuracy_against_live_model), skipped unless a model is configured,
because a unit suite must not depend on a GPU.
"""

from __future__ import annotations

import os

import pytest

from app.services.workbench import eval as wbeval
from app.services.workbench import router
from app.services.workbench.router import RouteDecision

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "routes.yaml")


def test_golden_file_is_wellformed():
    cases = wbeval.load_golden(GOLDEN)
    assert len(cases) >= 15
    for c in cases:
        assert c.question
        # Each case is either a dispatch (with sources) or an explicit refusal.
        assert c.expect_refuse or c.sources


class TestScorer:
    @pytest.mark.anyio
    async def test_a_perfect_router_scores_100(self, monkeypatch):
        cases = wbeval.load_golden(GOLDEN)

        async def oracle(question, *, role, pinned=None):
            case = next(c for c in cases if c.question == question)
            if case.expect_refuse:
                return RouteDecision(route="refuse", reason="unsafe")
            return RouteDecision(route="dispatch", sources=list(case.sources), intent=question)

        report = await wbeval.score(cases, oracle)
        assert report.total == len(cases)
        assert report.correct == report.total
        assert report.accuracy == 1.0
        assert report.failures == []

    @pytest.mark.anyio
    async def test_wrong_routes_are_counted_and_reported(self, monkeypatch):
        cases = wbeval.load_golden(GOLDEN)

        async def always_db(question, *, role, pinned=None):
            return RouteDecision(route="dispatch", sources=["db"], intent=question)

        report = await wbeval.score(cases, always_db)
        assert report.correct < report.total
        # Every non-db case is a failure, and each failure names what was expected vs got.
        assert report.failures
        f = report.failures[0]
        assert "expected" in f and "got" in f and "question" in f

    @pytest.mark.anyio
    async def test_set_equality_ignores_source_order(self, monkeypatch):
        cases = [wbeval.Case(id="x", question="q", sources=["macro", "db"], expect_refuse=False)]

        async def reversed_order(question, *, role, pinned=None):
            return RouteDecision(route="dispatch", sources=["db", "macro"], intent=question)

        report = await wbeval.score(cases, reversed_order)
        assert report.accuracy == 1.0


@pytest.mark.anyio
@pytest.mark.skipif(
    os.environ.get("WB_EVAL_LIVE") != "1",
    reason="live routing eval — set WB_EVAL_LIVE=1 with a model configured",
)
async def test_routing_accuracy_against_live_model():
    cases = wbeval.load_golden(GOLDEN)
    report = await wbeval.score(cases, router.route)
    # A regression gate, not a perfection gate: a catalog edit that drops accuracy is caught.
    assert report.accuracy >= 0.8, report.summary()
