from __future__ import annotations

import sys
from types import SimpleNamespace

from app.core.config import settings
from app.services import rag


def test_generate_with_groq_falls_back_after_primary_failure(monkeypatch):
    calls: list[str] = []

    class FakeRawResponse:
        headers: dict[str, str] = {}

        @staticmethod
        def parse():
            message = SimpleNamespace(content="secondary response")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeCompletions:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.with_raw_response = self

        def create(self, **_kwargs):
            calls.append(self.api_key)
            if self.api_key == "primary-key":
                raise RuntimeError("primary unavailable")
            return FakeRawResponse()

    class FakeGroq:
        def __init__(self, *, api_key: str):
            self.chat = SimpleNamespace(completions=FakeCompletions(api_key))

    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeGroq))
    monkeypatch.setattr(settings, "groq_api_key", "primary-key")
    monkeypatch.setattr(settings, "groq_api_key_secondary", "secondary-key")
    monkeypatch.setitem(rag._groq_state, "primary_blocked_until", 0.0)

    assert rag.generate_with_groq("summarize") == "secondary response"
    assert calls == ["primary-key", "secondary-key"]
