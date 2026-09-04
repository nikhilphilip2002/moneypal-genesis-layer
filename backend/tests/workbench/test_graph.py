"""The orchestrator, end to end, with the router and nodes stubbed. These tests assert the
frame protocol the frontend depends on and the two structural rules: every chosen source is
dispatched to its handler, and every usable turn emits one definitive answer.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.workbench import graph, models, nodes, router
from app.services.workbench.nodes import SourceResult
from app.services.workbench.results import Evidence
from tests.workbench.conftest import FakeLLM


@pytest.fixture(autouse=True)
def _memory_only_history(monkeypatch):
    """Graph protocol tests must not depend on the developer machine's remote Postgres."""
    monkeypatch.setattr(graph.history, "_ensure_table", lambda: False)
    graph.history._MEMORY.clear()
    yield
    graph.history._MEMORY.clear()


async def _collect(**kwargs) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    async for frame in graph.run_workbench(**kwargs):
        name = body = ""
        for line in frame.split("\n"):
            if line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: "):
                body += line[6:]
        if name:
            out.append((name, json.loads(body) if body else {}))
    return out


def _run(question="q", role="admin"):
    return _collect(
        question=question, conversation_id="c1", user="u", role=role,
        external_sources_enabled=True,
    )


def _stub_route(monkeypatch, decision):
    async def fake_route(question, *, role, pinned=None, history_messages=None, policy=None):
        return decision
    monkeypatch.setattr(router, "route", fake_route)


def _stub_node(monkeypatch, name, result):
    async def fake(*args, **kwargs):
        return result
    monkeypatch.setattr(nodes, name, fake)


def _names(events):
    return [n for n, _ in events]


class TestSingleSource:
    @pytest.mark.anyio
    async def test_streams_route_card_and_one_final_answer(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(route="dispatch", sources=["db"], intent="i"))
        _stub_node(monkeypatch, "run_db",
                   SourceResult(source="db", card_type="chart", payload={"title": "T"}, summary="s"))

        events = await _run()
        names = _names(events)
        assert "route" in names
        assert names.count("source_card") == 1
        answers = [data for name, data in events if name == "answer"]
        assert len(answers) == 1
        assert answers[0]["text"] == "s"
        assert names[-1] == "done"

    @pytest.mark.anyio
    async def test_source_failure_is_not_followed_by_a_second_generic_error(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db"], intent="i",
        ))
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="error",
            payload={"message": "The loan book could not answer that."},
        ))

        events = await _run()

        assert _names(events).count("source_card") == 1
        assert "error" not in _names(events)
        assert all(
            data.get("message") != "No intelligence source produced a usable answer."
            for _name, data in events
        )

    @pytest.mark.anyio
    async def test_db_receives_exact_user_question_not_router_paraphrase(self, monkeypatch):
        original = "principal amount paid by sheelavati"
        rewritten = "find total loan repayment for a named customer"
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db"], intent=rewritten,
        ))
        received = {}

        async def fake_db(question, **kwargs):
            received["question"] = question
            return SourceResult(
                source="db", card_type="chart", payload={"title": "Principal repaid"},
            )

        monkeypatch.setattr(nodes, "run_db", fake_db)
        await _run(question=original)

        assert received["question"] == original

    @pytest.mark.anyio
    async def test_db_receives_its_focused_task_for_a_hybrid_question(self, monkeypatch):
        original = "Compare our collection efficiency with peers"
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db", "competitive"], intent="compare",
            source_intents={
                "db": "show our collection efficiency",
                "competitive": "regional peer collection benchmarks",
            },
        ))
        received = {}

        async def fake_db(question, **kwargs):
            received["db"] = question
            return SourceResult(source="db", card_type="chart", payload={}, summary="98%")

        async def fake_competitive(question, **kwargs):
            received["competitive"] = question
            return SourceResult(source="competitive", card_type="brief", payload={}, summary="97%")

        monkeypatch.setattr(nodes, "run_db", fake_db)
        monkeypatch.setattr(nodes, "run_competitive", fake_competitive)
        monkeypatch.setattr(models, "for_step", lambda *a, **k: FakeLLM("98% versus 97%."))
        await _run(question=original)

        assert received == {
            "db": "show our collection efficiency",
            "competitive": "regional peer collection benchmarks",
        }


class TestDispatchTable:
    @pytest.mark.anyio
    async def test_every_chosen_source_is_dispatched_to_its_handler(self, monkeypatch):
        # The Phase 2 sources must each reach a real handler, not the unknown-source path.
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["competitive", "regulatory", "schema"], intent="i"))
        _stub_node(monkeypatch, "run_competitive",
                   SourceResult(source="competitive", card_type="brief", payload={"summary": "c"}))
        _stub_node(monkeypatch, "run_regulatory",
                   SourceResult(source="regulatory", card_type="brief", payload={"summary": "r"}))
        _stub_node(monkeypatch, "run_schema",
                   SourceResult(source="schema", card_type="schema", payload={"node_count": 3}))

        events = await _run()
        cards = [d for n, d in events if n == "source_card"]
        sources = {c["source"] for c in cards}
        assert sources == {"competitive", "regulatory", "schema"}
        # None fell through to an error card.
        assert all(c["card_type"] != "error" for c in cards)

    @pytest.mark.anyio
    async def test_web_source_reaches_the_public_handler_with_user_identity(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["web"], intent="latest RBI release",
        ))
        received = {}

        async def fake_web(intent, *, user, policy=None):
            received.update(intent=intent, user=user)
            return SourceResult(
                source="web", card_type="brief", payload={"summary": "fresh"},
                summary="fresh",
            )

        monkeypatch.setattr(nodes, "run_web", fake_web)
        events = await _run()

        assert received == {"intent": "latest RBI release", "user": "u"}
        card = next(data for name, data in events if name == "source_card")
        assert card["source"] == "web"

    @pytest.mark.anyio
    async def test_one_source_exception_does_not_fail_the_whole_turn(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["macro", "regulatory"], intent="i"))

        async def broken_macro(*args, **kwargs):
            raise TimeoutError("qdrant timed out")

        monkeypatch.setattr(nodes, "run_macro", broken_macro)
        _stub_node(monkeypatch, "run_regulatory",
                   SourceResult(source="regulatory", card_type="brief", payload={"summary": "r"}, summary="r"))

        events = await _run()
        cards = [data for name, data in events if name == "source_card"]

        assert {card["source"] for card in cards} == {"macro", "regulatory"}
        assert next(card for card in cards if card["source"] == "macro")["card_type"] == "error"
        assert "error" not in _names(events)
        assert _names(events)[-1] == "done"


class TestMultiSource:
    @pytest.mark.anyio
    async def test_two_contributing_sources_emit_one_merged_answer(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db", "macro"], intent="i"))
        _stub_node(monkeypatch, "run_db",
                   SourceResult(source="db", card_type="chart", payload={"title": "T"}, summary="book says X"))
        _stub_node(monkeypatch, "run_macro",
                   SourceResult(source="macro", card_type="brief", payload={"summary": "m"}, summary="market says Y"))
        monkeypatch.setattr(models, "for_step", lambda *a, **k: FakeLLM("A merged view."))

        events = await _run()
        answers = [d for n, d in events if n == "answer"]
        assert len(answers) == 1
        assert answers[0]["text"] == "A merged view."

    @pytest.mark.anyio
    async def test_single_vector_result_uses_exactly_one_common_composer_call(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["macro"], intent="GDP trend",
        ))
        _stub_node(monkeypatch, "run_macro", SourceResult(
            source="macro", card_type="brief", payload={"summary": "Retrieved evidence"},
            summary="Retrieved evidence",
            evidence=[Evidence("GDP grew 6.5%.", document="Official release")],
        ))
        fake = FakeLLM("GDP grew 6.5%.")
        monkeypatch.setattr(models, "for_step", lambda *args, **kwargs: fake)

        events = await _run()

        assert len(fake.calls) == 1
        assert fake.calls[0]["call_purpose"] == "final_compose"
        assert fake.calls[0]["max_output_tokens"] == graph.settings.workbench_composer_max_tokens
        assert next(data for name, data in events if name == "answer")["text"] == "GDP grew 6.5%."

    @pytest.mark.anyio
    async def test_multiple_vector_results_still_use_one_composer_call(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["macro", "regulatory"], intent="compare",
        ))
        _stub_node(monkeypatch, "run_macro", SourceResult(
            source="macro", card_type="brief", payload={}, summary="macro evidence",
            evidence=[Evidence("Inflation is 4.0%.", document="CPI")],
        ))
        _stub_node(monkeypatch, "run_regulatory", SourceResult(
            source="regulatory", card_type="brief", payload={}, summary="rule evidence",
            evidence=[Evidence("The limit is 10%.", document="RBI")],
        ))
        fake = FakeLLM("Inflation is 4.0%; the limit is 10%.")
        monkeypatch.setattr(models, "for_step", lambda *args, **kwargs: fake)

        await _run()

        assert len(fake.calls) == 1
        assert fake.calls[0]["call_purpose"] == "final_compose"

    @pytest.mark.anyio
    async def test_db_evidence_forces_common_composer_to_local_sensitive_mode(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db", "macro"], intent="compare",
        ))
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="chart", payload={}, summary="Our growth is 5%.",
            sensitive=True,
        ))
        _stub_node(monkeypatch, "run_macro", SourceResult(
            source="macro", card_type="brief", payload={}, summary="retrieved evidence",
            evidence=[Evidence("Market growth is 4%.", document="Official release")],
        ))
        seen = {}
        fake = FakeLLM("Our growth is 5% versus market growth of 4%.")

        def choose(step, *, sensitive):
            seen.update(step=step, sensitive=sensitive)
            return fake

        monkeypatch.setattr(models, "for_step", choose)

        await _run()

        assert seen == {"step": "synthesize", "sensitive": True}
        assert len(fake.calls) == 1

    @pytest.mark.anyio
    async def test_one_success_and_one_failure_emit_a_partial_answer(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db", "competitive"], intent="i"))
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="chart", payload={"title": "T"}, summary="book says X"))
        _stub_node(monkeypatch, "run_competitive", SourceResult(
            source="competitive", card_type="error", payload={"message": "offline"}))

        events = await _run()
        answer = next(data for name, data in events if name == "answer")
        assert answer["status"] == "partial"
        assert answer["text"] == "book says X"
        assert answer["unavailable_sources"][0]["source"] == "competitive"

    @pytest.mark.anyio
    async def test_incomplete_contributing_source_marks_answer_partial(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db", "macro"], intent="compare"))
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="chart", payload={}, summary="Our PAR 30 is 1.2%."))
        _stub_node(monkeypatch, "run_macro", SourceResult(
            source="macro", card_type="brief", payload={},
            summary="The requested benchmark is unavailable.", complete=False,
            limitation="SIDBI benchmark evidence is unavailable."))
        monkeypatch.setattr(models, "for_step", lambda *a, **k: FakeLLM("Our PAR 30 is 1.2%; no benchmark is available."))

        events = await _run()
        answer = next(data for name, data in events if name == "answer")
        assert answer["status"] == "partial"
        assert answer["limitations"] == [
            {"source": "macro", "reason": "SIDBI benchmark evidence is unavailable."}
        ]

    @pytest.mark.anyio
    async def test_stalled_composer_is_bounded_and_answer_is_marked_partial(
        self, monkeypatch
    ):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["macro"], intent="GDP trend",
        ))
        _stub_node(monkeypatch, "run_macro", SourceResult(
            source="macro", card_type="brief", payload={}, summary="GDP grew 6.5%.",
            evidence=[Evidence("GDP grew 6.5%.", document="Official release")],
        ))

        class Stalled(FakeLLM):
            async def complete(self, **kw):
                await asyncio.Event().wait()

        monkeypatch.setattr(models, "for_step", lambda *a, **k: Stalled())
        monkeypatch.setattr(graph.settings, "workbench_composer_timeout_s", 0.001)

        events = await _run()

        answer = next(data for name, data in events if name == "answer")
        assert answer["status"] == "partial"
        assert answer["text"] == "Macro: GDP grew 6.5%."
        assert answer["limitations"] == [{
            "source": "composer",
            "reason": "The answer composer was unavailable; showing retrieved evidence instead.",
        }]


class TestPinnedThreading:
    @pytest.mark.anyio
    async def test_a_pinned_source_is_threaded_into_routing(self, monkeypatch):
        # No router stub here: the real router runs, and a valid pin makes it dispatch to
        # exactly that source without a model call. This proves run_workbench forwards `pinned`.
        _stub_node(monkeypatch, "run_macro",
                   SourceResult(source="macro", card_type="brief", payload={"summary": "m"}))
        events = await _collect(
            question="q", conversation_id="c1", user="u", role="admin", pinned="macro",
            external_sources_enabled=True,
        )
        cards = [d for n, d in events if n == "source_card"]
        assert {c["source"] for c in cards} == {"macro"}


class TestRefuse:
    @pytest.mark.anyio
    async def test_a_router_refusal_emits_a_refusal_and_no_cards(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(route="refuse", reason="unsafe", message="no"))
        events = await _run()
        names = _names(events)
        assert "refusal" in names
        answer = next(data for name, data in events if name == "answer")
        assert answer["status"] == "refused"
        assert "source_card" not in names
        assert names[-1] == "done"


class TestOrchestratorSelection:
    @pytest.mark.anyio
    async def test_plain_async_path_preserves_event_contract(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db"], intent="i",
        ))
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="chart", payload={"title": "T"}, summary="answer",
        ))

        events = await _run()
        assert _names(events) == [
            "conversation", "stage", "stage", "route", "source_start", "source_card",
            "answer", "done",
        ]


class TestConsentAtEntryPoint:
    @pytest.mark.anyio
    async def test_default_off_external_pin_never_reaches_handler(self, monkeypatch):
        async def must_not_run(*_args, **_kwargs):  # pragma: no cover - call is failure
            raise AssertionError("external handler called")

        monkeypatch.setattr(nodes, "run_macro", must_not_run)
        events = await _collect(
            question="macro outlook", conversation_id="c1", user="u", role="admin",
            pinned="macro",
        )
        answer = next(data for name, data in events if name == "answer")
        assert answer["status"] == "refused"
        assert "source_card" not in _names(events)

    @pytest.mark.anyio
    async def test_default_off_mixed_question_runs_only_db_and_reports_gap(self, monkeypatch):
        fake = FakeLLM("unused")
        monkeypatch.setattr(models, "for_step", lambda *args, **kwargs: fake)
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="chart", payload={}, summary="Loan growth is 5%.",
        ))
        async def must_not_run(*_args, **_kwargs):  # pragma: no cover - call is failure
            raise AssertionError("external handler called")
        monkeypatch.setattr(nodes, "run_macro", must_not_run)

        events = await _collect(
            question="Compare our loan growth with inflation",
            conversation_id="c1", user="u", role="admin",
        )
        cards = [data for name, data in events if name == "source_card"]
        answer = next(data for name, data in events if name == "answer")
        assert [card["source"] for card in cards] == ["db"]
        assert answer["status"] == "partial"
        assert answer["limitations"]
        assert fake.calls == []


class TestResilience:
    @pytest.mark.anyio
    async def test_closing_before_orchestration_marks_turn_partial(self):
        stream = graph.run_workbench(
            question="q", conversation_id="cancel-early", user="u", role="admin",
        )
        assert "event: conversation" in await anext(stream)
        await stream.aclose()

        record = graph.history.get("cancel-early", user="u")
        assert record is not None
        assert record.turns[0]["status"] == "partial"

    @pytest.mark.anyio
    async def test_closing_during_dispatch_cancels_and_persists_partial(self, monkeypatch):
        import asyncio

        entered = asyncio.Event()
        release = asyncio.Event()
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db"], intent="q",
        ))

        async def waiting_db(*args, **kwargs):
            entered.set()
            await release.wait()
            return SourceResult(source="db", card_type="chart", payload={}, summary="answer")

        monkeypatch.setattr(nodes, "run_db", waiting_db)
        stream = graph.run_workbench(
            question="q", conversation_id="cancel-dispatch", user="u", role="admin",
        )
        while True:
            frame = await anext(stream)
            if "event: source_start" in frame:
                break
        await entered.wait()
        await stream.aclose()
        await asyncio.sleep(0)

        record = graph.history.get("cancel-dispatch", user="u")
        assert record is not None
        assert record.turns[0]["status"] == "partial"

    @pytest.mark.anyio
    async def test_answer_stream_survives_history_write_failure(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db"], intent="q",
        ))
        _stub_node(monkeypatch, "run_db", SourceResult(
            source="db", card_type="chart", payload={}, summary="answer",
        ))
        monkeypatch.setattr(
            graph.history, "set_answer",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
        )

        events = await _collect(
            question="q", conversation_id="history-failure", user="u", role="admin",
            external_sources_enabled=True,
        )

        assert next(data for name, data in events if name == "answer")["text"] == "answer"
        assert events[-1][0] == "done"
