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
    async def test_parses_source_specific_hybrid_tasks(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["db","competitive"],"intent":"compare",'
            '"source_intents":{"db":"show our collection efficiency",'
            '"competitive":"regional peer collection benchmarks"}}'
        ))
        decision = await router.route(
            "How does our collection efficiency compare with peer benchmarks?", role="admin",
        )
        assert decision.source_intents["db"] == "show our collection efficiency"
        assert decision.source_intents["competitive"] == "regional peer collection benchmarks"

    @pytest.mark.anyio
    async def test_hybrid_coverage_guard_adds_missed_external_source(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["db"],"intent":"our collection efficiency"}'
        ))
        decision = await router.route(
            "How does our collection efficiency compare with NBFC peers?", role="admin",
        )
        assert decision.sources == ["db", "competitive"]
        assert "compare" not in decision.source_intents["db"].lower()

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

    @pytest.mark.anyio
    async def test_session_history_precedes_the_current_question(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}')
        _use(monkeypatch, fake)
        history_messages = [
            {"role": "user", "content": "What is PAR 30?"},
            {"role": "assistant", "content": "PAR 30 is 4.2%."},
        ]

        await router.route(
            "and by branch?", role="admin", history_messages=history_messages,
        )

        sent = fake.calls[0]["messages"]
        assert sent[-3:] == [*history_messages, {"role": "user", "content": "and by branch?"}]

    @pytest.mark.anyio
    async def test_lending_typos_are_normalized_before_routing(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}')
        _use(monkeypatch, fake)

        await router.route("intrest rate based on schema name", role="admin")

        assert fake.calls[0]["messages"][-1]["content"] == "interest rate based on scheme name"

    @pytest.mark.anyio
    async def test_real_database_schema_word_is_not_changed(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["schema"],"intent":"x"}')
        _use(monkeypatch, fake)

        await router.route("show the schema table relationships", role="admin")

        assert fake.calls[0]["messages"][-1]["content"] == "show the schema table relationships"

    @pytest.mark.anyio
    async def test_descriptive_catalog_question_uses_concept_source(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}'))

        decision = await router.route("What does interest rate mean?", role="admin")

        assert decision.sources == ["knowledge"]

    @pytest.mark.anyio
    async def test_rate_values_stay_on_loan_book_source(self, monkeypatch):
        _use(
            monkeypatch,
            FakeLLM('{"route":"dispatch","sources":["knowledge"],"intent":"x"}'),
        )

        decision = await router.route("What are the various intrest rates?", role="admin")

        assert decision.sources == ["db"]


class TestRefuse:
    @pytest.mark.anyio
    async def test_parses_a_refusal(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"refuse","reason":"unsafe","message":"no"}'))
        decision = await router.route("delete everything", role="admin")
        assert decision.route == "refuse"
        assert decision.reason == "unsafe"

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "question",
        ["top 10 agents", "Show borrowers with zero outstanding principal"],
    )
    async def test_catalogued_loan_book_subject_overrides_hallucinated_refusal(
        self, monkeypatch, question
    ):
        _use(
            monkeypatch,
            FakeLLM('{"route":"refuse","reason":"out_of_scope","message":"missing"}'),
        )
        decision = await router.route(question, role="admin")
        assert decision.route == "dispatch"
        assert decision.sources == ["db"]
        assert decision.model == "catalog"


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
    async def test_llm_failure_still_routes_both_halves_of_a_hybrid_question(self, monkeypatch):
        class Failing(FakeLLM):
            async def complete(self, **kw):
                raise LLMError("model down")

        _use(monkeypatch, Failing())
        decision = await router.route(
            "Compare our collection efficiency with NBFC peers", role="admin",
        )
        assert decision.sources == ["db", "competitive"]
        assert decision.source_intents["db"] == "Show our collection efficiency by product and branch."

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
