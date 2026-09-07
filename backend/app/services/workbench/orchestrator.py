"""Plain-async Workbench orchestration.

Streaming, persistence, cancellation, telemetry, and post-turn compaction remain owned by
``run_workbench`` at its stable import path. Dispatch retains concurrent fan-out.
"""

from __future__ import annotations

from app.services.workbench import router
from app.services.workbench.graph import (
    WorkbenchState,
    answer_results,
    dispatch_sources,
    select_sources,
)


async def _run_legacy(state: WorkbenchState) -> None:
    state.update(await select_sources(state))
    state.update(await dispatch_sources(state))
    state.update(await answer_results(state))


async def run(state: WorkbenchState) -> None:
    from app.services.workbench import agent

    mode = agent.assigned_mode(state.get("conversation_id", ""), state.get("user", ""))
    if mode == "shadow":
        await agent.shadow(state)
        await _run_legacy(state)
        return
    if mode == "on":
        if state.get("question") and state.get("source_policy") is not None and router.requires_mandatory_preflight(
            state["question"],
            pinned=state.get("pinned"),
            history_messages=state.get("history_messages", []),
            policy=state["source_policy"],
        ):
            await _run_legacy(state)
            return
        try:
            await agent.run(state)
            return
        except Exception:
            # Rollout degradation returns to the separately governed legacy workflow.
            # It never parses assistant content or emulates a native tool call with JSON.
            import logging

            logging.getLogger(__name__).exception(
                "native agent path failed; using governed legacy orchestrator"
            )
    await _run_legacy(state)


__all__ = ["run"]
