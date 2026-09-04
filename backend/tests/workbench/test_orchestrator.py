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
