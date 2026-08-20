"""The morning read: what is notable, and what to do about it, for one desk.

This is where the four engines meet. Signals say what changed, analyses say where the book
stands, worklists say who to call. A persona decides the order and nothing else.

Why a persona may not change a number is worth restating here, because this is the module
where it would be tempting: the same book looks different from five desks, but PAR 30 is PAR
30 at every one of them. A persona that quietly redefined a metric or narrowed a filter would
give two people different answers to the same question with no way to discover why — the
fastest way to lose a finance team's trust in a reporting product. It reorders and preselects.
That is the whole contract.

The signals lead deliberately. A briefing that opens with seven KPI tiles asks the reader to
work out what matters; one that opens with "two things need attention" has already done it,
and the tiles are underneath for whoever wants them.
"""

from __future__ import annotations

import concurrent.futures
import logging
from datetime import date, datetime, timezone

from app.services.nlq import analysis as analysis_service
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import (
    AnalysisResult,
    Briefing,
    Period,
    Signal,
    Worklist,
)
from app.services.nlq.narrator import humanize_label
from app.services.signals import store

logger = logging.getLogger(__name__)

MAX_SIGNALS = 5
""""The five things I need to know" is the actual ask, and a briefing that lists everything
has ranked nothing."""

MAX_WORKERS = 2
"""A briefing runs several analyses and a worklist. Kept small: this is a background read on
a shared pool, not the thing a user is waiting on."""


class BriefingError(ValueError):
    """A persona that does not exist."""


def personas(catalog: Catalog | None = None):
    return (catalog or get_catalog()).personas.values()


def build(
    persona_id: str,
    *,
    catalog: Catalog | None = None,
    today: date | None = None,
    role: str | None = None,
    include_worklists: bool = True,
) -> Briefing:
    """Assemble one desk's morning read."""
    cat = catalog or get_catalog()
    persona = cat.personas.get(persona_id)
    if persona is None:
        raise BriefingError(f"unknown persona {persona_id!r}")

    signals = _signals_for(persona, cat)
    analyses, worklists, warnings = _run(persona, cat, today, role, include_worklists)

    return Briefing(
        persona=persona.id,
        label=persona.label,
        generated_at=datetime.now(timezone.utc),
        headline=_headline(signals, analyses, persona.label),
        signals=signals,
        analyses=analyses,
        worklists=worklists,
        warnings=warnings,
    )


def _signals_for(persona, cat: Catalog) -> list[Signal]:
    """This desk's scopes, plus data health.

    Freshness is shown to everyone regardless of persona. A stale table quietly makes every
    other number on the page wrong, and there is no desk for which that is somebody else's
    problem.
    """
    scoped = store.open_signals(scopes=list(persona.signal_scopes), limit=MAX_SIGNALS)
    health = [
        s for s in store.open_signals(limit=MAX_SIGNALS)
        if s.signal.kind == "data_health"
    ]
    merged = {s.signal.fingerprint: s for s in (*health, *scoped)}
    rank = {"alert": 0, "watch": 1, "info": 2}
    ordered = sorted(
        merged.values(), key=lambda s: (rank.get(s.signal.severity, 2), -abs(s.signal.magnitude))
    )
    out = []
    for stored in ordered[:MAX_SIGNALS]:
        signal = stored.signal.model_copy(update={"status": stored.status})
        if stored.is_standing:
            # A problem that has been there a week is a different conversation from one that
            # appeared last night, and the difference is invisible without saying it.
            signal.text = f"{signal.text} Standing since {stored.first_seen_at:%d %b}."
        out.append(signal)
    return out


def _run(
    persona, cat: Catalog, today: date | None, role: str | None, include_worklists: bool
) -> tuple[list[AnalysisResult], list[Worklist], list[str]]:
    from app.services import worklists as worklist_service

    period = Period(relative=persona.default_period)  # type: ignore[arg-type]
    warnings: list[str] = []

    def run_analysis(analysis_id: str):
        spec = analysis_service.build(analysis_id, catalog=cat, period=period)
        return analysis_service.run(spec, catalog=cat, today=today, role=role)

    def run_worklist(worklist_id: str):
        return worklist_service.build(worklist_id, catalog=cat, as_of=today, role=role)

    analyses: list[AnalysisResult] = []
    lists: list[Worklist] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        analysis_futures = {
            pool.submit(run_analysis, a): a for a in persona.analyses if a in cat.analyses
        }
        worklist_futures = {}
        if include_worklists:
            worklist_futures = {
                pool.submit(run_worklist, w): w
                for w in persona.worklists
                if w in cat.worklists.presets
            }

        # One failed section does not lose the briefing. A director with four of five
        # sections and a named gap is far better served than one with an error page.
        for future, analysis_id in analysis_futures.items():
            try:
                analyses.append(future.result())
            except Exception as exc:  # noqa: BLE001
                logger.warning("briefing analysis %s failed: %s", analysis_id, exc)
                warnings.append(f"{analysis_id.replace('_', ' ')} could not be prepared.")
        for future, worklist_id in worklist_futures.items():
            try:
                lists.append(future.result())
            except Exception as exc:  # noqa: BLE001
                logger.warning("briefing worklist %s failed: %s", worklist_id, exc)
                warnings.append(f"{worklist_id.replace('_', ' ')} could not be prepared.")

    # Preserve the persona's declared order rather than whatever finished first.
    order = {a: i for i, a in enumerate(persona.analyses)}
    analyses.sort(key=lambda a: order.get(a.id, len(order)))
    list_order = {w: i for i, w in enumerate(persona.worklists)}
    lists.sort(key=lambda w: list_order.get(w.id, len(list_order)))
    return analyses, lists, warnings


def _headline(signals: list[Signal], analyses: list[AnalysisResult], label: str) -> str:
    """Deterministic, and never model-written.

    Says what is wrong, or says plainly that nothing is — and distinguishes "nothing is
    wrong" from "the scan has not run", because a reader who cannot tell those apart will
    assume the first.
    """
    alerts = [s for s in signals if s.severity == "alert"]
    watches = [s for s in signals if s.severity == "watch"]

    if alerts:
        named = ", ".join(humanize_label(s.label) for s in alerts[:3])
        return f"{len(alerts)} thing{'s' if len(alerts) > 1 else ''} need attention: {named}."
    if watches:
        named = ", ".join(humanize_label(s.label) for s in watches[:3])
        return f"Nothing urgent. Worth watching: {named}."
    if analyses:
        return f"No open signals for {label}. The indicators below are the current picture."
    return (
        "No signals and no indicators are available. The scan may not have run yet — "
        "this is not the same as a clean book."
    )


__all__ = ["MAX_SIGNALS", "BriefingError", "build", "personas"]
