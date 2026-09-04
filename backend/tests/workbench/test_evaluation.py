import pytest

from app.services.workbench import evaluation, router
from app.services.workbench.access import build_policy
from tests.workbench.conftest import FakeLLM


@pytest.mark.anyio
async def test_route_fixture_accuracy_and_router_avoidance(monkeypatch):
    fake = FakeLLM('{"route":"refuse","reason":"ambiguous","message":"clarify"}')
    monkeypatch.setattr(router.models, "for_step", lambda *args, **kwargs: fake)
    correct = 0
    total = 0
    for fixture in evaluation.ROUTE_FIXTURES:
        decision = await router.route(
            fixture.question,
            role="admin",
            pinned=fixture.pinned,
            history_messages=[{"role": role, "content": text} for role, text in fixture.history],
            policy=build_policy(role="admin", external_sources_enabled=True),
        )
        total += 1
        correct += tuple(decision.sources) == fixture.sources
    assert correct / total >= 0.95
    assert len(fake.calls) / total <= 0.20


@pytest.mark.anyio
@pytest.mark.parametrize("source,question", [
    ("macro", "Explain Karnataka GDP trends"),
    ("competitive", "Who are the competing NBFC lenders?"),
    ("regulatory", "What do RBI prudential guidelines require?"),
    ("web", "Search the web for the latest RBI announcement"),
])
async def test_external_fixture_off_is_deterministic_denial(monkeypatch, source, question):
    class MustNotRun:
        async def complete(self, **kwargs):  # pragma: no cover
            raise AssertionError("router model called")

    monkeypatch.setattr(router.models, "for_step", lambda *args, **kwargs: MustNotRun())
    decision = await router.route(
        question, role="admin",
        policy=build_policy(role="admin", external_sources_enabled=False),
    )
    assert decision.route == "refuse"
    assert decision.reason == "external_consent_required"
    assert source not in decision.effective_sources


def test_usage_summary_reports_p50_p95_by_purpose():
    report = evaluation.usage_summary([{
        "usage": {"calls": [
            {"purpose": "route", "uncached_prompt_tokens": 100},
            {"purpose": "route", "uncached_prompt_tokens": 200},
        ]},
        "timing": {"first_event_ms": 1, "first_card_ms": 10, "total_ms": 20},
    }])
    assert report["purposes"]["route"] == {
        "count": 2, "p50_uncached": 100.0, "p95_uncached": 200.0,
    }
