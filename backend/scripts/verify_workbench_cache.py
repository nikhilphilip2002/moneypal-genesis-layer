from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

from .verify_workbench_rollout import ask, request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--question",
        default="Show the total number of loan accounts as a KPI.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-cache-hits", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("WORKBENCH_API_TOKEN", "")
    if not token:
        parser.error("Set WORKBENCH_API_TOKEN to an authorized API token")
    base = args.base_url.rstrip("/")
    conversations = {
        name: f"cache-check-{uuid.uuid4().hex[:12]}" for name in ("a", "b")
    }
    cases = [
        ("first_turn", "a", args.question),
        (
            "followup",
            "a",
            "Show that same result as a table without querying again.",
        ),
        ("other_conversation", "b", "What is a loan account?"),
        (
            "return_to_conversation",
            "a",
            "Show that previous result as a KPI without querying again.",
        ),
    ]
    report = {"cases": [], "passed": True}
    for label, name, question in cases:
        started = time.perf_counter()
        events = ask(
            base, token, question=question, conversation_id=conversations[name]
        )
        duration = int((time.perf_counter() - started) * 1000)
        conversation = request_json(
            f"{base}/workbench/conversations/{conversations[name]}", token
        )
        turn = conversation["turns"][-1]
        usage = turn.get("usage") or {}
        errors = [
            payload.get("code")
            for event, payload in events
            if event == "error"
        ]
        answered = any(
            event == "answer"
            and payload.get("status") in {"answered", "partial"}
            for event, payload in events
        )
        cached = int(usage.get("cached_prompt_tokens") or 0)
        passed = (
            answered
            and not errors
            and (
                not args.require_cache_hits
                or label not in {"followup", "return_to_conversation"}
                or cached > 0
            )
        )
        report["cases"].append(
            {
                "case": label,
                "conversation_id": conversations[name],
                "duration_ms": duration,
                "cached_prompt_tokens": cached,
                "uncached_prompt_tokens": usage.get("uncached_prompt_tokens"),
                "model_calls": usage.get("calls", []),
                "errors": errors,
                "passed": passed,
            }
        )
        report["passed"] = report["passed"] and passed
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
