from __future__ import annotations

from types import SimpleNamespace

from app.core.config import settings
from app.services import rag


def test_generate_uses_the_configured_openai_endpoint(monkeypatch):
    seen: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            seen["request"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="configured response")
                )]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

        def close(self):
            seen["closed"] = True

    monkeypatch.setattr(rag, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(settings, "llm_base_url", "http://model.test/v1")
    monkeypatch.setattr(settings, "llm_api_key", "secret")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    assert rag.generate_with_llm("summarize") == "configured response"
    assert seen["client"]["base_url"] == "http://model.test/v1/"
    assert seen["client"]["api_key"] == "secret"
    assert seen["client"]["max_retries"] == 0
    assert seen["request"]["model"] == "test-model"
    assert seen["closed"] is True
