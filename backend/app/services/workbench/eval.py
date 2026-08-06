"""Routing eval — measures whether the router sends questions to the right source(s).

This is the discipline that keeps "don't hardcode the questions" honest: the router decides
from the source-catalog descriptions, and this harness scores those decisions against a
golden set. When accuracy drops after a catalog edit, the fix goes back into the catalog
descriptions or the few-shots — never into a per-question rule in the router.

The scorer is model-agnostic: it takes any `route_fn(question, *, role) -> RouteDecision`, so
the same harness scores a live model, a stubbed one in tests, or a future rules baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

import yaml

from app.services.workbench.router import RouteDecision


@dataclass(slots=True)
class Case:
    id: str
    question: str
    sources: list[str] = field(default_factory=list)
    expect_refuse: bool = False
    category: str = ""


@dataclass(slots=True)
class EvalReport:
    total: int
    correct: int
    failures: list[dict]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def summary(self) -> str:
        lines = [f"routing accuracy: {self.correct}/{self.total} = {self.accuracy:.1%}"]
        for f in self.failures:
            lines.append(f"  ✗ {f['question']!r}: expected {f['expected']}, got {f['got']}")
        return "\n".join(lines)


def load_golden(path: str) -> list[Case]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or []
    cases: list[Case] = []
    for entry in raw:
        cases.append(Case(
            id=entry["id"],
            question=entry["question"],
            sources=list(entry.get("sources", []) or []),
            expect_refuse=entry.get("route") == "refuse",
            category=entry.get("category", ""),
        ))
    return cases


def _expected(case: Case) -> str:
    return "refuse" if case.expect_refuse else "+".join(sorted(case.sources))


def _got(decision: RouteDecision) -> str:
    return "refuse" if decision.route == "refuse" else "+".join(sorted(decision.sources))


async def score(cases: list[Case], route_fn: Callable[..., Awaitable[RouteDecision]],
                *, role: str = "admin") -> EvalReport:
    """Run every case through `route_fn` and score on set-equality of the outcome.

    A dispatch case is correct when the dispatched source set equals the expected set; a
    refusal case is correct when the router refuses. Order never matters.
    """
    correct = 0
    failures: list[dict] = []
    for case in cases:
        decision = await route_fn(case.question, role=role)
        expected, got = _expected(case), _got(decision)
        if expected == got:
            correct += 1
        else:
            failures.append({"id": case.id, "question": case.question,
                             "expected": expected, "got": got})
    return EvalReport(total=len(cases), correct=correct, failures=failures)


def _default_golden() -> str:
    import os

    return os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "tests", "workbench", "golden", "routes.yaml",
    )


async def _run_cli(path: str) -> int:
    """Score the golden set against the live router. `python -m app.services.workbench.eval`."""
    from app.services.workbench import router

    cases = load_golden(path)
    report = await score(cases, router.route)
    print(report.summary())
    return 0 if report.accuracy >= 0.8 else 1


if __name__ == "__main__":
    import asyncio
    import sys

    golden = sys.argv[1] if len(sys.argv) > 1 else _default_golden()
    raise SystemExit(asyncio.run(_run_cli(golden)))
