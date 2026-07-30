"""Golden-set evaluation harness.

Scoring is on **execution match**, not string match: two QuerySpecs are equivalent if they
produce the same result set. Many spellings of the same question are correct, and grading
on spec equality would punish the planner for choosing `fy_to_date` where the author wrote
an explicit date range that resolves to the same window.

Run it:
    python -m app.services.nlq.eval                # whole set
    python -m app.services.nlq.eval --category refuse
    python -m app.services.nlq.eval --limit 20 --pace 2.0

`--pace` exists because the development provider rate-limits aggressively; it has no
bearing on production behaviour.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import CompileError, bind, compile_spec
from app.services.nlq.contracts import QuerySpec
from app.services.nlq.llm.prompts import PROMPT_VERSION
from app.services.nlq.planner import plan

logger = logging.getLogger(__name__)

# backend/app/services/nlq/eval.py -> backend/tests/nlq/golden/questions.yaml
GOLDEN_PATH = Path(__file__).resolve().parents[3] / "tests" / "nlq" / "golden" / "questions.yaml"


@dataclass(slots=True)
class CaseResult:
    id: str
    question: str
    category: str
    expected_route: str
    actual_route: str
    route_match: bool
    execution_match: bool | None = None  # None when not applicable
    reason_match: bool | None = None
    detail: str = ""
    duration_ms: int = 0
    attempts: int = 1

    @property
    def passed(self) -> bool:
        if not self.route_match:
            return False
        if self.execution_match is False:
            return False
        if self.reason_match is False:
            return False
        return True


@dataclass(slots=True)
class EvalReport:
    results: list[CaseResult] = field(default_factory=list)
    prompt_version: str = PROMPT_VERSION
    model: str = ""
    provider: str = ""

    @property
    def accuracy(self) -> float:
        return sum(r.passed for r in self.results) / len(self.results) if self.results else 0.0

    def by_category(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for result in self.results:
            bucket = out.setdefault(result.category, {"total": 0, "passed": 0})
            bucket["total"] += 1
            bucket["passed"] += int(result.passed)
        for bucket in out.values():
            bucket["accuracy"] = bucket["passed"] / bucket["total"]
        return out

    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "cases": len(self.results),
            "prompt_version": self.prompt_version,
            "model": self.model,
            "provider": self.provider,
            "by_category": self.by_category(),
            "failures": [
                {
                    "id": r.id,
                    "question": r.question,
                    "expected": r.expected_route,
                    "actual": r.actual_route,
                    "detail": r.detail,
                }
                for r in self.failures()
            ],
        }


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    return yaml.safe_load((path or GOLDEN_PATH).read_text(encoding="utf-8"))


def results_equivalent(expected: QuerySpec, actual: QuerySpec, cursor) -> tuple[bool, str]:
    """Execution match: do both specs return the same rows?

    Falls back to comparing the compiled SQL when no cursor is available, which is weaker
    but still catches a planner that picked a different metric.
    """
    try:
        expected_sql = compile_spec(expected)
        actual_sql = compile_spec(actual)
    except CompileError as exc:
        return False, f"compile failed: {exc}"

    if cursor is None:
        same = expected_sql.sql == actual_sql.sql
        return same, "" if same else "SQL differs (no database available to compare results)"

    try:
        rows_expected = _run(cursor, expected_sql)
        rows_actual = _run(cursor, actual_sql)
    except Exception as exc:  # noqa: BLE001
        return False, f"execution failed: {type(exc).__name__}: {exc}"

    if rows_expected == rows_actual:
        return True, ""
    return False, (
        f"different results: expected {len(rows_expected)} rows, got {len(rows_actual)}"
    )


def _run(cursor, compiled) -> list[tuple]:
    sql, params = bind(compiled.sql, compiled.params)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    # Normalise: order is a presentation concern, not a correctness one.
    return sorted(tuple(str(v) for v in row) for row in rows)


async def evaluate(
    cases: list[dict[str, Any]] | None = None,
    *,
    cursor=None,
    pace: float = 0.0,
) -> EvalReport:
    catalog = get_catalog()
    cases = cases or load_cases()
    report = EvalReport()

    for case in cases:
        started = time.perf_counter()
        try:
            outcome = await plan(case["question"], catalog=catalog)
        except Exception as exc:  # noqa: BLE001
            report.results.append(
                CaseResult(
                    id=case["id"],
                    question=case["question"],
                    category=case["category"],
                    expected_route=case["route"],
                    actual_route="error",
                    route_match=False,
                    detail=f"{type(exc).__name__}: {exc}"[:200],
                )
            )
            if pace:
                await asyncio.sleep(pace)
            continue

        report.model = outcome.model or report.model
        report.provider = outcome.provider or report.provider
        actual = outcome.plan
        result = CaseResult(
            id=case["id"],
            question=case["question"],
            category=case["category"],
            expected_route=case["route"],
            actual_route=actual.route,
            route_match=actual.route == case["route"],
            duration_ms=int((time.perf_counter() - started) * 1000),
            attempts=outcome.attempts,
        )

        if result.route_match and actual.route == "queryspec" and case.get("spec"):
            expected_spec = QuerySpec.model_validate(case["spec"])
            match, detail = results_equivalent(expected_spec, actual.spec, cursor)
            result.execution_match = match
            result.detail = detail
        elif result.route_match and actual.route == "refuse" and case.get("reason"):
            result.reason_match = actual.reason == case["reason"]
            if not result.reason_match:
                result.detail = f"expected reason {case['reason']}, got {actual.reason}"
        elif not result.route_match:
            result.detail = f"routed {actual.route}, expected {case['route']}"

        report.results.append(result)
        if pace:
            await asyncio.sleep(pace)

    return report


def _print(report: EvalReport) -> None:
    print(f"\nGolden set: {len(report.results)} cases")
    print(f"Model:      {report.provider}/{report.model}  prompt={report.prompt_version}")
    print(f"Accuracy:   {report.accuracy:.1%}\n")
    print(f"{'category':16} {'passed':>8} {'total':>6} {'accuracy':>9}")
    for name, bucket in sorted(report.by_category().items()):
        print(f"{name:16} {bucket['passed']:>8} {bucket['total']:>6} {bucket['accuracy']:>8.0%}")
    failures = report.failures()
    if failures:
        print(f"\n{len(failures)} failures:")
        for result in failures:
            print(f"  {result.id} [{result.category}] {result.question}")
            print(f"      expected={result.expected_route} actual={result.actual_route} "
                  f"{result.detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the planner against the golden set")
    parser.add_argument("--category", help="only run one category")
    parser.add_argument("--limit", type=int, help="only run the first N cases")
    parser.add_argument("--pace", type=float, default=0.0, help="seconds between calls")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--no-db", action="store_true", help="skip execution match")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    cases = load_cases()
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    if args.limit:
        cases = cases[: args.limit]

    cursor = None
    connection = None
    if not args.no_db:
        try:
            from app.services.db_schema import get_connection

            connection = get_connection()
            cursor = connection.cursor()
        except Exception as exc:  # noqa: BLE001
            print(f"(no database: falling back to SQL comparison — {exc})")

    try:
        report = asyncio.run(evaluate(cases, cursor=cursor, pace=args.pace))
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print(report)


if __name__ == "__main__":
    main()
