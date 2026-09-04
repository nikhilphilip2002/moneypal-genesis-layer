"""The router turns a question into a set of sources. The tests hold two lines that matter
most: it can never route to a source the role may not see (access control), and a routing
failure degrades to a sensible default rather than a dead end.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.nlq.llm import LLMError
from app.services.workbench import models, router
from tests.workbench.conftest import FakeLLM


def _use(monkeypatch, client):
    monkeypatch.setattr(models, "for_step", lambda *a, **k: client)


class TestDispatch:
    @pytest.mark.anyio
    async def test_agent_name_request_is_a_record_request_not_a_concept(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["knowledge"],"intent":"explain agent name"}'
        ))

        decision = await router.route("give the agents name instead of id", role="admin")

        assert decision.sources == ["db"]

    @pytest.mark.anyio
    async def test_branch_directory_request_is_not_routed_to_concepts(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["knowledge"],"intent":"define branch"}'
        ))

        decision = await router.route("what are the branches is there", role="admin")

        assert decision.sources == ["db"]

    @pytest.mark.anyio
    async def test_named_borrower_disbursement_date_is_not_routed_to_concepts(
        self, monkeypatch
    ):
        fake = FakeLLM(
            '{"route":"dispatch","sources":["knowledge"],"intent":"define date"}'
        )
        _use(monkeypatch, fake)

        decision = await router.route(
            "what is the disbursment date of customer SHEELAVATHI M K", role="admin"
        )

        assert decision.sources == ["db"]
        assert decision.model == "catalog"
        assert fake.calls == []

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "question",
        ["what is the today's GDP", "what is the today GDP of karnataka"],
    )
    async def test_plain_gdp_question_overrides_an_incorrect_loan_book_route(
        self, monkeypatch, question
    ):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["db"],"intent":"current GDP"}'
        ))

        decision = await router.route(question, role="admin")

        assert decision.sources == ["web"]

    @pytest.mark.anyio
    async def test_latest_official_release_overrides_stale_model_route(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["macro"],"intent":"repo rate"}'
        ))

        decision = await router.route(
            "What is the latest RBI repo rate announcement?", role="admin"
        )

        assert decision.sources == ["web"]
        assert decision.source_intents["web"] == "What is the latest RBI repo rate announcement?"

    @pytest.mark.anyio
    async def test_stable_macro_question_stays_on_local_index(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["macro"],"intent":"Karnataka GDP trend"}'
        ))

        decision = await router.route("Explain Karnataka GDP growth trends", role="admin")

        assert decision.sources == ["macro"]

    @pytest.mark.anyio
    async def test_fresh_hybrid_query_is_split_between_db_and_public_web(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["db"],"intent":"compare loan growth"}'
        ))

        decision = await router.route(
            "Compare our loan growth against the latest RBI bank credit growth", role="admin"
        )

        assert decision.sources == ["db", "web"]
        assert "our" in decision.source_intents["db"].lower()
        assert "our" not in decision.source_intents["web"].lower()
        assert "RBI" in decision.source_intents["web"]

    @pytest.mark.anyio
    async def test_gdp_comparison_with_our_book_keeps_both_sources(self, monkeypatch):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["db"],"intent":"compare"}'
        ))

        decision = await router.route(
            "Compare Karnataka GDP growth with our loan portfolio growth", role="admin"
        )

        assert decision.sources == ["db", "macro"]

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
        assert decision.sources == ["db", "competitive"]
        assert "collection efficiency" in decision.source_intents["db"].lower()
        assert decision.model == "deterministic"

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
        # The open-access rollout makes governed loan-book lookups visible to this role.
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":["db","macro"],"intent":"x"}'))
        decision = await router.route("q", role="gicc_policy")
        assert decision.sources == ["db", "macro"]

    @pytest.mark.anyio
    async def test_deduplicates_preserving_order(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":["macro","macro","competitive"],"intent":"x"}'))
        decision = await router.route("q", role="admin")
        assert decision.sources == ["macro", "competitive"]

    @pytest.mark.anyio
    async def test_structural_db_followup_bypasses_router_model(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}')
        _use(monkeypatch, fake)
        history_messages = [
            {"role": "user", "content": "What is PAR 30?"},
            {"role": "assistant", "content": "PAR 30 is 4.2%."},
        ]

        decision = await router.route(
            "and by branch?", role="admin", history_messages=history_messages,
        )

        assert decision.sources == ["db"]
        assert decision.source_intents["db"] == "What is PAR 30 by branch?"
        assert fake.calls == []

    @pytest.mark.anyio
    async def test_structural_followup_ignores_checkpoint_system_messages(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}')
        _use(monkeypatch, fake)

        decision = await router.route(
            "and by branch?",
            role="admin",
            history_messages=[
                {"role": "system", "content": "Conversation checkpoint"},
                {"role": "system", "content": "Current session state"},
                {"role": "user", "content": "Show PAR 30"},
                {"role": "assistant", "content": "PAR 30 was 4.2%."},
            ],
        )

        assert decision.sources == ["db"]
        assert fake.calls == []

    @pytest.mark.anyio
    async def test_lending_typos_are_normalized_before_routing(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"x"}')
        _use(monkeypatch, fake)

        await router.route("intrest rate based on schema name", role="admin")

        assert fake.calls == []

    @pytest.mark.anyio
    async def test_real_database_schema_word_is_not_changed(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["schema"],"intent":"x"}')
        _use(monkeypatch, fake)

        await router.route("show the schema table relationships", role="admin")

        assert fake.calls == []

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

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "question",
        [
            "what is the total amount of equity shares",
            "what is the capital share",
            "what is the total capital reserve sharesz",
            "which agent under more loan accounts is ther",
            "how many agriculturist loan accounts is theer",
            "what is the name of product code 16 in loan book",
            "what is the sanction amount of agent 45",
        ],
    )
    async def test_governed_business_values_override_concept_or_refusal(
        self, monkeypatch, question
    ):
        _use(monkeypatch, FakeLLM(
            '{"route":"dispatch","sources":["knowledge"],"intent":"define it"}'
        ))

        decision = await router.route(question, role="admin")

        assert decision.sources == ["db"]


class TestRefuse:
    @pytest.mark.anyio
    async def test_destructive_database_request_is_refused_without_a_model_call(
        self, monkeypatch
    ):
        fake = FakeLLM('{"route":"dispatch","sources":["db"],"intent":"unsafe"}')
        _use(monkeypatch, fake)

        decision = await router.route("Drop the loan accounts table", role="admin")

        assert decision.route == "refuse"
        assert decision.reason == "unsafe_operation"
        assert fake.calls == []

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
        assert decision.model in {"catalog", "deterministic"}


class TestFallback:
    @pytest.mark.anyio
    async def test_overlapping_external_cues_select_each_required_source(self, monkeypatch):
        fake = FakeLLM('{"route":"refuse","reason":"wrong","message":"wrong"}')
        _use(monkeypatch, fake)

        decision = await router.route(
            "Compare competitor positioning under RBI prudential rules and GDP conditions",
            role="admin",
        )

        assert decision.sources == ["competitive", "regulatory", "macro"]
        assert fake.calls == []

    @pytest.mark.anyio
    async def test_role_restriction_excludes_unavailable_competitive_source(
        self, monkeypatch
    ):
        fake = FakeLLM('{"route":"dispatch","sources":["competitive"],"intent":"peers"}')
        _use(monkeypatch, fake)

        from app.services.workbench.access import build_policy

        decision = await router.route(
            "Who are our NBFC competitors?",
            role="gicc_director",
            policy=build_policy(role="gicc_director", external_sources_enabled=True),
        )

        assert decision.route == "dispatch"
        assert decision.sources == ["db"]
        assert decision.limitations == [{
            "source": "competitive",
            "reason": (
                "The requested external source is unavailable, so this answer includes "
                "only the supported loan-book portion."
            ),
        }]
        assert "competitive" not in decision.effective_sources
        assert fake.calls == []

    @pytest.mark.anyio
    async def test_deterministic_selector_can_be_disabled_independently(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["macro"],"intent":"GDP trend"}')
        _use(monkeypatch, fake)
        monkeypatch.setattr(router.settings, "workbench_deterministic_routing", False)

        decision = await router.route("Explain Karnataka GDP trends", role="admin")

        assert decision.sources == ["macro"]
        assert len(fake.calls) == 1

    @pytest.mark.anyio
    async def test_llm_failure_clarifies_an_ambiguous_request(self, monkeypatch):
        class Failing(FakeLLM):
            async def complete(self, **kw):
                raise LLMError("model down")

        _use(monkeypatch, Failing())
        decision = await router.route("q", role="admin")
        assert decision.route == "refuse"
        assert decision.reason == "clarification_required"

    @pytest.mark.anyio
    async def test_stalled_llm_is_bounded_and_uses_fallback(self, monkeypatch):
        class Stalled(FakeLLM):
            async def complete(self, **kw):
                await asyncio.Event().wait()

        _use(monkeypatch, Stalled())
        monkeypatch.setattr(router.settings, "workbench_router_timeout_s", 0.001)

        decision = await router.route("q", role="admin")

        assert decision.route == "refuse"
        assert decision.reason == "clarification_required"
        assert decision.fallback_used is True
        assert decision.ambiguity_class == "router_failure"

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
    async def test_llm_failure_still_routes_latest_public_fact_to_web(self, monkeypatch):
        class Failing(FakeLLM):
            async def complete(self, **kw):
                raise LLMError("model down")

        _use(monkeypatch, Failing())
        decision = await router.route("latest MoSPI CPI announcement", role="admin")

        assert decision.sources == ["web"]

    @pytest.mark.anyio
    async def test_llm_failure_does_not_force_db_during_open_access(self, monkeypatch):
        class Failing(FakeLLM):
            async def complete(self, **kw):
                raise LLMError("model down")

        _use(monkeypatch, Failing())
        decision = await router.route("q", role="gicc_policy")
        assert decision.route == "refuse"
        assert decision.reason == "clarification_required"

    @pytest.mark.anyio
    async def test_empty_source_list_clarifies_rather_than_forcing_a_source(self, monkeypatch):
        _use(monkeypatch, FakeLLM('{"route":"dispatch","sources":[],"intent":"x"}'))
        decision = await router.route("q", role="admin")
        assert decision.route == "refuse"
        assert decision.reason == "clarification_required"


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
    async def test_open_access_role_can_pin_the_loan_book(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["macro"],"intent":"x"}')
        _use(monkeypatch, fake)
        decision = await router.route("q", role="gicc_policy", pinned="db")
        assert decision.sources == ["db"]
        assert fake.calls == []

    @pytest.mark.anyio
    async def test_an_unknown_pin_is_rejected(self, monkeypatch):
        fake = FakeLLM('{"route":"dispatch","sources":["macro"],"intent":"x"}')
        _use(monkeypatch, fake)
        decision = await router.route("q", role="admin", pinned="not_a_source")
        assert decision.route == "refuse"
        assert decision.reason == "source_unavailable"
