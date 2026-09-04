#!/usr/bin/env python3
"""Smoke and policy verification against a deployed Workbench API.

Example:
  python backend/scripts/verify_workbench_rollout.py \
    --base-url http://backend:8000 --token mock-token-moneypal_admin --include-web
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any


def request_json(url: str, token: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - operator URL
        return json.load(response)


def ask(base_url: str, token: str, **payload: Any) -> list[tuple[str, dict[str, Any]]]:
    request = urllib.request.Request(
        f"{base_url}/workbench/ask",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    events: list[tuple[str, dict[str, Any]]] = []
    with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310 - operator URL
        event = ""
        data: list[str] = []
        for raw in response:
            line = raw.decode().rstrip("\r\n")
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data.append(line[6:])
            elif not line and event:
                events.append((event, json.loads("".join(data) or "{}")))
                event, data = "", []
    return events


def percentile(values: list[int], percent: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percent))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--include-web", action="store_true")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    conversation_id = f"rollout-{uuid.uuid4().hex[:10]}"
    report: dict[str, Any] = {"conversation_id": conversation_id, "cases": []}

    sources = request_json(f"{base_url}/workbench/sources", args.token)["sources"]
    available = {item["id"] for item in sources if item.get("deployment_available")}
    cases = [
        ("db_off", "Show our total principal outstanding", False, "db"),
        ("macro_off", "Explain Karnataka GDP growth trends", False, None),
        ("macro_on", "Explain Karnataka GDP growth trends", True, "macro"),
    ]
    if args.include_web and "web" in available:
        cases.append(("web_on", "Search the web for the latest RBI repo announcement", True, "web"))

    for case_id, question, enabled, expected_source in cases:
        events = ask(
            base_url, args.token, question=question, conversation_id=conversation_id,
            external_sources_enabled=enabled,
        )
        cards = [data.get("source") for name, data in events if name == "source_card"]
        answer = next((data for name, data in events if name == "answer"), {})
        if expected_source is None:
            forbidden = {"macro", "competitive", "regulatory", "web"} & set(cards)
            if forbidden:
                raise AssertionError(f"{case_id}: consent-off connector card(s): {sorted(forbidden)}")
            if answer.get("status") != "refused":
                raise AssertionError(f"{case_id}: expected deterministic consent refusal")
        elif expected_source not in cards:
            raise AssertionError(f"{case_id}: expected {expected_source}, got {cards}")
        report["cases"].append({
            "id": case_id, "external_sources_enabled": enabled, "cards": cards,
            "answer_status": answer.get("status"), "events": [name for name, _ in events],
        })

    conversation = request_json(
        f"{base_url}/workbench/conversations/{conversation_id}", args.token,
    )
    turns = conversation.get("turns", [])
    model_calls = [int((turn.get("usage") or {}).get("model_call_count", 0)) for turn in turns]
    uncached = [int((turn.get("usage") or {}).get("uncached_prompt_tokens", 0)) for turn in turns]
    total_ms = [int((turn.get("timing") or {}).get("total_ms", 0)) for turn in turns]
    report["telemetry"] = {
        "turns": len(turns),
        "median_model_calls": statistics.median(model_calls) if model_calls else 0,
        "p50_uncached_tokens": percentile(uncached, 0.50),
        "p95_uncached_tokens": percentile(uncached, 0.95),
        "p50_total_ms": percentile(total_ms, 0.50),
        "p95_total_ms": percentile(total_ms, 0.95),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, urllib.error.URLError) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
