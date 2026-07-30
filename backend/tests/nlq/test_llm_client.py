"""Tests for the provider abstraction.

No network: every call is served by a stub transport. The point of these is that provider
differences stay inside client.py — the pipeline above it must never learn which model it
is talking to.
"""

import json

import httpx
import pytest

from app.services.nlq.llm.client import (
    GROQ_BASE_URL,
    LLMError,
    LLMResult,
    LLMTimeout,
    LLMUnavailable,
    OpenAICompatibleClient,
    _ProviderProfile,
    get_llm_client,
)

SCHEMA = {"title": "PlanResult", "type": "object", "properties": {"route": {"type": "string"}}}


def _client(handler, *, supports_json_schema=True, name="llamacpp", max_retries=1):
    profile = _ProviderProfile(
        name=name,
        base_url="http://stub/v1",
        api_key="k",
        supports_json_schema=supports_json_schema,
        health_path="/health",
    )
    client = OpenAICompatibleClient(profile=profile, model="m", max_retries=max_retries)
    client._client = httpx.AsyncClient(
        base_url="http://stub/v1", transport=httpx.MockTransport(handler)
    )
    return client


def _ok(content="{}"):
    return httpx.Response(
        200,
        json={
            "model": "m",
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        },
    )


class TestJsonSalvage:
    """Only the non-grammar providers need this; it must never mangle valid JSON."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ('{"route":"refuse"}', {"route": "refuse"}),
            ('```json\n{"route":"refuse"}\n```', {"route": "refuse"}),
            ('Sure! {"route":"refuse"} hope that helps', {"route": "refuse"}),
            ('  \n {"a": {"b": 1}} \n ', {"a": {"b": 1}}),
        ],
    )
    def test_parses(self, raw, expected):
        assert LLMResult(text=raw, model="m", provider="p").json() == expected

    def test_raises_on_prose(self):
        with pytest.raises(LLMError):
            LLMResult(text="I cannot help with that.", model="m", provider="p").json()


class TestResponseFormat:
    @pytest.mark.anyio
    async def test_json_schema_is_passed_when_supported(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok('{"route":"refuse"}')

        client = _client(handler, supports_json_schema=True)
        await client.complete(messages=[{"role": "user", "content": "hi"}], json_schema=SCHEMA)
        assert seen["response_format"]["type"] == "json_schema"
        assert seen["response_format"]["json_schema"]["schema"] == SCHEMA
        assert seen["response_format"]["json_schema"]["strict"] is True

    @pytest.mark.anyio
    async def test_degrades_to_json_mode_when_unsupported(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok('{"route":"refuse"}')

        client = _client(handler, supports_json_schema=False, name="groq")
        await client.complete(messages=[{"role": "user", "content": "hi"}], json_schema=SCHEMA)
        assert seen["response_format"] == {"type": "json_object"}

    @pytest.mark.anyio
    async def test_temperature_defaults_to_zero(self):
        """Translation, not authorship — a nonzero default would make plans nondeterministic."""
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok()

        await _client(handler).complete(messages=[{"role": "user", "content": "hi"}])
        assert seen["temperature"] == 0.0
        assert seen["stream"] is False


class TestFailureHandling:
    @pytest.mark.anyio
    async def test_retries_on_503_then_succeeds(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(503) if calls["n"] == 1 else _ok('{"ok":true}')

        result = await _client(handler, max_retries=1).complete(
            messages=[{"role": "user", "content": "hi"}]
        )
        assert calls["n"] == 2
        assert result.json() == {"ok": True}

    @pytest.mark.anyio
    async def test_does_not_retry_4xx(self):
        """A 400 is a request bug (bad schema, wrong model) — retrying just repeats it."""
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(400, text="unknown model")

        with pytest.raises(LLMError):
            await _client(handler).complete(messages=[{"role": "user", "content": "hi"}])
        assert calls["n"] == 1

    @pytest.mark.anyio
    async def test_timeout_surfaces_as_llmtimeout(self):
        def handler(request):
            raise httpx.ReadTimeout("too slow")

        with pytest.raises(LLMTimeout):
            await _client(handler, max_retries=0).complete(
                messages=[{"role": "user", "content": "hi"}]
            )

    @pytest.mark.anyio
    async def test_transport_error_surfaces_as_unavailable(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        with pytest.raises(LLMUnavailable):
            await _client(handler, max_retries=0).complete(
                messages=[{"role": "user", "content": "hi"}]
            )


class TestHealth:
    """Health must never raise — the ask bar's offline state is driven by it."""

    @pytest.mark.anyio
    async def test_ok(self):
        assert (await _client(lambda r: httpx.Response(200)).health())["status"] == "ok"

    @pytest.mark.anyio
    async def test_unreachable_is_down_not_an_exception(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        assert (await _client(handler).health())["status"] == "down"

    @pytest.mark.anyio
    async def test_error_status_is_degraded(self):
        assert (await _client(lambda r: httpx.Response(500)).health())["status"] == "degraded"


class TestProviderSelection:
    def test_llamacpp_health_path_sits_above_v1(self):
        client = get_llm_client("llamacpp")
        assert client.profile.health_path.endswith("/health")
        assert "/v1/health" not in client.profile.health_path

    def test_groq_profile(self):
        client = get_llm_client("groq")
        assert client.profile.base_url == GROQ_BASE_URL
        assert client.profile.supports_json_schema is False

    def test_unknown_provider_is_rejected(self):
        with pytest.raises(LLMUnavailable):
            get_llm_client("openai")
