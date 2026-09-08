"""Score the deployed model's native tool selection over the Gold question set.

This is intentionally opt-in and read-only: it calls the configured LLM but never executes
the selected database tool. Run from ``backend`` after loading the deployment environment:

    python -m scripts.evaluate_native_agent
    python -m scripts.evaluate_native_agent --limit 12
    python -m scripts.evaluate_native_agent --view gold.semantic_repayment_event
    python -m scripts.evaluate_native_agent --model /models/qwen.gguf --one-per-view
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.services.workbench import access, agent, models


DEFAULT_GOLDEN = (
    Path(__file__).parents[1] / "tests" / "workbench" / "golden" / "agent_questions.yaml"
)


@dataclass(frozen=True, slots=True)
class PromptCase:
    id: str
    view: str
    prompt: str
    tool: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    tables: tuple[str, ...]


def load_cases(path: Path) -> list[PromptCase]:
    families = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [
        PromptCase(
            id=f"{family['id']}:{index + 1}",
            view=family["view"],
            prompt=prompt,
            tool=family["tool"],
            metrics=tuple(family.get("metrics", ())),
            dimensions=tuple(family.get("dimensions", ())),
            tables=tuple(family.get("tables", ())),
        )
        for family in families
        for index, prompt in enumerate(family["prompts"])
    ]


def score_call(case: PromptCase, calls: list[Any]) -> tuple[bool, str]:
    if len(calls) != 1:
        return False, f"expected one {case.tool} call, got {[call.name for call in calls]}"
    call = calls[0]
    if call.name != case.tool:
        return False, f"expected {case.tool}, got {call.name}"
    if case.tool == "query_metrics":
        actual_metrics = set(call.arguments.get("metrics", ()))
        actual_dimensions = set(call.arguments.get("dimensions", ()))
        if actual_metrics != set(case.metrics):
            return False, f"metrics expected {case.metrics}, got {sorted(actual_metrics)}"
        if actual_dimensions != set(case.dimensions):
            return False, f"dimensions expected {case.dimensions}, got {sorted(actual_dimensions)}"
    if case.tool == "run_validated_query":
        actual_tables = set(call.arguments.get("tables", ()))
        if actual_tables != set(case.tables):
            return False, f"tables expected {case.tables}, got {sorted(actual_tables)}"
    return True, ""


async def evaluate(
    cases: list[PromptCase], *, model_override: str | None = None,
) -> dict[str, Any]:
    rows = []
    policy = access.build_policy(role="admin", external_sources_enabled=True)
    client = models.for_step("route", sensitive=True)
    configured_model = client.model
    if model_override:
        client.model = model_override
    for position, case in enumerate(cases, start=1):
        state = {
            "question": case.prompt,
            "history_messages": [],
            "source_policy": policy,
        }
        started = time.perf_counter()
        try:
            result = await agent.select_calls(state)
            passed, error = score_call(case, result.tool_calls)
            response_model = result.model
            calls = [
                {"name": call.name, "arguments": call.arguments}
                for call in result.tool_calls
            ]
        except Exception as exc:  # noqa: BLE001 - eval records protocol failures
            passed, error, calls = False, f"{type(exc).__name__}: {exc}", []
            response_model = None
        row = {
            "id": case.id,
            "view": case.view,
            "prompt": case.prompt,
            "passed": passed,
            "error": error,
            "calls": calls,
            "response_model": response_model,
            "duration_s": round(time.perf_counter() - started, 3),
        }
        rows.append(row)
        marker = "PASS" if passed else "FAIL"
        print(f"[{position}/{len(cases)}] {marker} {case.id}: {error or case.prompt}", flush=True)

    passed = sum(row["passed"] for row in rows)
    client.model = configured_model
    return {
        "requested_model": model_override or configured_model,
        "total": len(rows),
        "passed": passed,
        "accuracy": passed / len(rows) if rows else 0.0,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--view")
    parser.add_argument("--family")
    parser.add_argument("--one-per-view", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--model",
        help=(
            "OpenAI-compatible model id to send for this evaluation. The endpoint must "
            "already serve it; this does not load or switch server models."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_cases(args.golden)
    if args.view:
        cases = [case for case in cases if case.view == args.view]
    if args.family:
        cases = [case for case in cases if case.id.split(":", 1)[0] == args.family]
    if args.one_per_view:
        first_by_view: dict[str, PromptCase] = {}
        for case in cases:
            first_by_view.setdefault(case.view, case)
        cases = list(first_by_view.values())
    if args.limit is not None:
        cases = cases[: max(args.limit, 0)]
    report = asyncio.run(evaluate(cases, model_override=args.model))
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        f"model: {report['requested_model']}\n"
        f"accuracy: {report['passed']}/{report['total']} = {report['accuracy']:.1%}",
        flush=True,
    )
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
