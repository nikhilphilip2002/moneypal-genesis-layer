from __future__ import annotations

import httpx

from app.core.config import settings
from app.services import rag


def test_generate_uses_the_configured_openai_endpoint(monkeypatch):
    seen: dict = {}

    def fake_post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": "configured response"}}]},
        )

    monkeypatch.setattr(rag.httpx if hasattr(rag, "httpx") else httpx, "post", fake_post)
    monkeypatch.setattr(settings, "llm_base_url", "http://model.test/v1")
    monkeypatch.setattr(settings, "llm_api_key", "secret")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    assert rag.generate_with_llm("summarize") == "configured response"
    assert seen["url"] == "http://model.test/v1/chat/completions"
    assert seen["json"]["model"] == "test-model"
    assert seen["headers"]["Authorization"] == "Bearer secret"
