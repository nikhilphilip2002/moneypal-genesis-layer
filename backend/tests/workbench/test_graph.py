"""The orchestrator, end to end, with the router and nodes stubbed. These tests assert the
frame protocol the frontend depends on and the two structural rules: every chosen source is
dispatched to its handler, and a merged synthesis is emitted only when more than one source
actually contributed.
"""

from __future__ import annotations

import json

import pytest

from app.services.workbench import graph, models, nodes, router
from app.services.workbench.nodes import SourceResult
from tests.workbench.conftest import FakeLLM


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
    return _collect(question=question, conversation_id="c1", user="u", role=role)


def _stub_route(monkeypatch, decision):
    async def fake_route(question, *, role, pinned=None):
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
    async def test_streams_route_then_a_single_card_and_no_synthesis(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(route="dispatch", sources=["db"], intent="i"))
        _stub_node(monkeypatch, "run_db",
                   SourceResult(source="db", card_type="chart", payload={"title": "T"}, summary="s"))

        events = await _run()
        names = _names(events)
        assert "route" in names
        assert names.count("source_card") == 1
        assert "synthesis" not in names
        assert names[-1] == "done"


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


class TestMultiSource:
    @pytest.mark.anyio
    async def test_two_contributing_sources_emit_a_merged_synthesis(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(
            route="dispatch", sources=["db", "macro"], intent="i"))
        _stub_node(monkeypatch, "run_db",
                   SourceResult(source="db", card_type="chart", payload={"title": "T"}, summary="book says X"))
        _stub_node(monkeypatch, "run_macro",
                   SourceResult(source="macro", card_type="brief", payload={"summary": "m"}, summary="market says Y"))
        monkeypatch.setattr(models, "for_step", lambda *a, **k: FakeLLM("A merged view."))

        events = await _run()
        synth = [d for n, d in events if n == "synthesis"]
        assert len(synth) == 1
        assert synth[0]["text"] == "A merged view."


class TestPinnedThreading:
    @pytest.mark.anyio
    async def test_a_pinned_source_is_threaded_into_routing(self, monkeypatch):
        # No router stub here: the real router runs, and a valid pin makes it dispatch to
        # exactly that source without a model call. This proves run_workbench forwards `pinned`.
        _stub_node(monkeypatch, "run_macro",
                   SourceResult(source="macro", card_type="brief", payload={"summary": "m"}))
        events = await _collect(question="q", conversation_id="c1", user="u", role="admin", pinned="macro")
        cards = [d for n, d in events if n == "source_card"]
        assert {c["source"] for c in cards} == {"macro"}


class TestRefuse:
    @pytest.mark.anyio
    async def test_a_router_refusal_emits_a_refusal_and_no_cards(self, monkeypatch):
        _stub_route(monkeypatch, router.RouteDecision(route="refuse", reason="unsafe", message="no"))
        events = await _run()
        names = _names(events)
        assert "refusal" in names
        assert "source_card" not in names
        assert names[-1] == "done"
