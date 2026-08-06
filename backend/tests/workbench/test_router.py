"""The router turns a question into a set of sources. The tests hold two lines that matter
most: it can never route to a source the role may not see (access control), and a routing
failure degrades to a sensible default rather than a dead end.
"""

from __future__ import annotations

import pytest

from app.services.nlq.llm import LLMError
from app.services.workbench import models, router
from tests.workbench.conftest import FakeLLM


def _use(monkeypatch, client):
    monkeypatch.setattr(models, "for_step", lambda *a, **k: client)


class TestDispatch:
    @pytest.mark.anyio
    async def test_parses_chosen_sources(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":["db","macro"],"intent":"x"}'))
        decision = await router.route("q", role="admin")
        assert decision.route == "dispatch"
        assert decision.sources == ["db", "macro"]

    @pytest.mark.anyio
    async def test_strips_sources_the_role_may_not_see(self, monkeypatch):
        # gicc_policy cannot see the loan book; a model that names it must not leak it.
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":["db","macro"],"intent":"x"}'))
        decision = await router.route("q", role="gicc_policy")
        assert decision.sources == ["macro"]

    @pytest.mark.anyio
    async def test_deduplicates_preserving_order(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":["macro","macro","competitive"],"intent":"x"}'))
        decision = await router.route("q", role="admin")
        assert decision.sources == ["macro", "competitive"]


class TestRefuse:
    @pytest.mark.anyio
    async def test_parses_a_refusal(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"refuse","reason":"unsafe","message":"no"}'))
        decision = await router.route("delete everything", role="admin")
        assert decision.route == "refuse"
        assert decision.reason == "unsafe"


class TestFallback:
    @pytest.mark.anyio
    async def test_llm_failure_falls_back_to_the_loan_book_for_a_book_role(self, monkeypatch):
        class Failing(FakeLLM):
            async def complete(self, **kw):
                raise LLMError("model down")

        _use(monkeypatch, Failing())
        decision = await router.route("q", role="admin")
        assert decision.route == "dispatch"
        assert decision.sources == ["db"]

    @pytest.mark.anyio
    async def test_llm_failure_falls_back_to_first_visible_for_a_non_book_role(self, monkeypatch):
        class Failing(FakeLLM):
            async def complete(self, **kw):
                raise LLMError("model down")

        _use(monkeypatch, Failing())
        decision = await router.route("q", role="gicc_policy")
        # gicc_policy has no db; the fallback must be a source it can actually see.
        assert decision.route == "dispatch"
        assert decision.sources and decision.sources[0] in {"macro", "competitive", "regulatory"}

    @pytest.mark.anyio
    async def test_empty_source_list_falls_back_rather_than_returning_nothing(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":[],"intent":"x"}'))
        decision = await router.route("q", role="admin")
        assert decision.sources == ["db"]


class TestPinnedSource:
    @pytest.mark.anyio
    async def test_a_valid_pin_bypasses_the_model_entirely(self, monkeypatch):
        # Pinning is a deterministic override: the user has already chosen the source, so
        # there is nothing for the router to decide and no model call to make.
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}')
        _use(monkeypatch, fake)
        decision = await router.route("q", role="admin", pinned="macro")
        assert decision.sources == ["macro"]
        assert fake.calls == []  # the model was never consulted

    @pytest.mark.anyio
    async def test_a_pin_the_role_cannot_see_is_ignored_and_routing_proceeds(self, monkeypatch):
        # gicc_policy cannot see the loan book; a pinned "db" must not smuggle it in. The pin
        # is dropped and normal routing runs.
        fake = FakeLLM('{"route":"dispatch","sources":["macro"],"intent":"x"}')
        _use(monkeypatch, fake)
        decision = await router.route("q", role="gicc_policy", pinned="db")
        assert decision.sources == ["macro"]
        assert fake.calls  # routing ran because the pin was rejected

    @pytest.mark.anyio
    async def test_an_unknown_pin_is_ignored(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["macro"],"intent":"x"}')
        _use(monkeypatch, fake)
        decision = await router.route("q", role="admin", pinned="not_a_source")
        assert decision.sources == ["macro"]
