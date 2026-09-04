"""Plain-async Workbench orchestration.

Streaming, persistence, cancellation, telemetry, and post-turn compaction remain owned by
``run_workbench`` at its stable import path. Dispatch retains concurrent fan-out.
"""

from __future__ import annotations

from app.services.workbench.graph import (
    WorkbenchState,
    answer_results,
    dispatch_sources,
    select_sources,
)


async def run(state: WorkbenchState) -> None:
    state.update(await select_sources(state))
    state.update(await dispatch_sources(state))
    state.update(await answer_results(state))


__all__ = ["run"]
