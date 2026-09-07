from __future__ import annotations

import pytest

from app.services.workbench import orchestrator


@pytest.mark.anyio
async def test_plain_orchestrator_runs_select_dispatch_answer_in_order(monkeypatch):
    seen: list[str] = []

    async def select(state):
        seen.append("select")
        return {"decision": "chosen"}

    async def dispatch(state):
        assert state["decision"] == "chosen"
        seen.append("dispatch")
        return {"results": ["result"]}

    async def answer(state):
        assert state["results"] == ["result"]
        seen.append("answer")
        return {}

    monkeypatch.setattr(orchestrator, "select_sources", select)
    monkeypatch.setattr(orchestrator, "dispatch_sources", dispatch)
    monkeypatch.setattr(orchestrator, "answer_results", answer)
    state = {}
    await orchestrator.run(state)  # type: ignore[arg-type]
    assert seen == ["select", "dispatch", "answer"]


@pytest.mark.anyio
async def test_plain_orchestrator_propagates_for_entry_point_error_handling(monkeypatch):
    async def broken(_state):
        raise RuntimeError("boom")

    monkeypatch.setattr(orchestrator, "select_sources", broken)
    with pytest.raises(RuntimeError, match="boom"):
        await orchestrator.run({})  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_agent_mode_delegates_without_running_legacy_steps(monkeypatch):
    from app.services.workbench import agent

    seen = []

    async def native(state):
        seen.append(("agent", state["conversation_id"]))

    async def legacy(_state):  # pragma: no cover - call is failure
        raise AssertionError("legacy path must not run")

    monkeypatch.setattr(agent, "assigned_mode", lambda *_args: "on")
    monkeypatch.setattr(agent, "run", native)
    monkeypatch.setattr(orchestrator, "select_sources", legacy)
    await orchestrator.run({"conversation_id": "c1", "user": "alice"})  # type: ignore[arg-type]
    assert seen == [("agent", "c1")]


@pytest.mark.anyio
async def test_shadow_selects_but_preserves_legacy_path(monkeypatch):
    from app.services.workbench import agent

    seen = []

    async def shadow(state):
        seen.append("shadow")

    async def select(state):
        seen.append("legacy")
        return {"decision": "chosen"}

    async def dispatch(state):
        return {"results": []}

    async def answer(state):
        return {}

    monkeypatch.setattr(agent, "assigned_mode", lambda *_args: "shadow")
    monkeypatch.setattr(agent, "shadow", shadow)
    monkeypatch.setattr(orchestrator, "select_sources", select)
    monkeypatch.setattr(orchestrator, "dispatch_sources", dispatch)
    monkeypatch.setattr(orchestrator, "answer_results", answer)
    await orchestrator.run({"conversation_id": "c1", "user": "alice"})  # type: ignore[arg-type]
    assert seen == ["shadow", "legacy"]
