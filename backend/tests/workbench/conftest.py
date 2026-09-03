"""Fixtures for the workbench suite.

The workbench modules are pure-logic where they can be: sources and router parsing take no
network, so most tests need only a fake LLM client. `FakeLLM` returns a canned completion so
router and synthesis behaviour can be asserted deterministically without a live model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@dataclass
class FakeResult:
    text: str
    model: str = "fake-local"
    provider: str = "llamacpp"

    def json(self) -> Any:
        import json

        return json.loads(self.text)


@dataclass
class FakeLLM:
    """Stands in for OpenAICompatibleClient. Records calls; returns a scripted text."""

    reply: str = "{}"
    calls: list[dict] = None  # type: ignore[assignment]

    def __post_init__(self):
        self.calls = []

    async def complete(self, *, messages, json_schema=None, timeout_s=None):
        self.calls.append({"messages": messages, "json_schema": json_schema})
        return FakeResult(text=self.reply)

    async def health(self):
        return {"status": "ok"}
