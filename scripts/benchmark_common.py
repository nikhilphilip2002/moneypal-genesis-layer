"""Shared configuration, transport, and statistics helpers for benchmarks."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_env_file(path: Path | None) -> dict[str, str]:
    """Load simple KEY=VALUE configuration without application dependencies."""
    candidates = [
        path,
        Path(".env.prod"),
        Path(__file__).resolve().parents[1] / ".env.prod",
        Path(".env"),
    ]
    target = next(
        (
            candidate
            for candidate in candidates
            if candidate and candidate.is_file()
        ),
        None,
    )
    if target is None:
        return {}

    values: dict[str, str] = {}
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def decode_sse_data(data_lines: list[str]) -> dict[str, Any]:
    raw = "\n".join(data_lines)
    try:
        value = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"raw": raw}
    return value if isinstance(value, dict) else {"value": value}


def stream_sse(
    url: str,
    payload: dict[str, Any],
    *,
    token: str,
    timeout_s: int,
    user_agent: str,
) -> tuple[list[tuple[str, dict[str, Any]]], str, float]:
    """POST a JSON payload and return parsed SSE events, error text, and latency."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
    )
    events: list[tuple[str, dict[str, Any]]] = []
    error = ""
    started = time.monotonic()
    timeout = timeout_s if timeout_s > 0 else None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            event_name = ""
            data_lines: list[str] = []
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip(
                    "\r\n"
                )
                if not line:
                    if event_name:
                        events.append(
                            (event_name, decode_sse_data(data_lines))
                        )
                        if event_name == "done":
                            break
                    event_name, data_lines = "", []
                elif line.startswith("event:"):
                    event_name = line.partition(":")[2].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.partition(":")[2].lstrip())
            if event_name and (not events or events[-1][0] != event_name):
                events.append((event_name, decode_sse_data(data_lines)))
    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        error = f"Connection error: {exc.reason}"
    except TimeoutError:
        error = f"Request timed out after {timeout_s}s"
    except Exception as exc:  # noqa: BLE001 - benchmarks record failures and continue
        error = f"Unexpected error: {exc}"
    return events, error, time.monotonic() - started


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]
