"""Tests for the provider abstraction.

No network: every call is served by a stub transport. The point of these is that provider
differences stay inside client.py — the pipeline above it must never learn which model it
is talking to.
"""

import asyncio
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
from app.services.nlq.llm.telemetry import collect_calls

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


class TestThinkingModels:
    """A hybrid-reasoning model that thinks past its token budget answers 200 OK with an
    empty `content` and the whole trace in `reasoning_content`. That produced a planner
    demotion to text-to-SQL and, to the user, "not answerable from the loan book"."""

    def test_empty_content_names_the_cause(self):
        result = LLMResult(
            text="",
            model="m",
            provider="llamacpp",
            finish_reason="length",
            reasoning="Here's a thinking process: " + "x" * 2000,
        )
        with pytest.raises(LLMError) as exc:
            result.json()
        message = str(exc.value)
        assert "no content" in message
        assert "reasoning" in message
        assert "length" in message

    @pytest.mark.anyio
    async def test_reasoning_content_is_captured(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "model": "m",
                    "choices": [
                        {
                            "message": {"content": "", "reasoning_content": "thinking..."},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 700},
                },
            )

        result = await _client(handler).complete(messages=[{"role": "user", "content": "hi"}])
        assert result.text == ""
        assert result.reasoning == "thinking..."

    @pytest.mark.anyio
    async def test_llamacpp_cache_and_thinking_controls_are_sent(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok('{"route":"refuse"}')

        await _client(handler).complete(messages=[{"role": "user", "content": "hi"}])
        assert seen["chat_template_kwargs"] == {"enable_thinking": False}
        assert seen["cache_prompt"] is True
        assert "n_cache_reuse" not in seen
        assert "temperature" not in seen
        assert "max_tokens" not in seen

    @pytest.mark.anyio
    async def test_groq_does_not_receive_llamacpp_extensions(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok('{"route":"refuse"}')

        await _client(handler, name="groq").complete(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert "chat_template_kwargs" not in seen
        assert "cache_prompt" not in seen

    @pytest.mark.anyio
    async def test_local_requests_are_serialized(self, monkeypatch, tmp_path):
        from app.core.config import settings
        from app.services.nlq import ratelimit

        ratelimit.reset()
        monkeypatch.setattr(settings, "nlq_llm_lock_path", tmp_path / "llama.lock")
        active = 0
        peak = 0

        async def handler(_request):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.03)
            active -= 1
            return _ok()

        client = _client(handler, max_retries=0)
        await asyncio.gather(*(
            client.complete(messages=[{"role": "user", "content": str(index)}])
            for index in range(2)
        ))
        await client.aclose()
        ratelimit.reset()
        assert peak == 1

    @pytest.mark.anyio
    async def test_explicit_output_budget_is_sent_as_standard_max_tokens(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok()

        await _client(handler).complete(
            messages=[{"role": "user", "content": "hi"}], max_output_tokens=300,
        )
        assert seen["max_tokens"] == 300

    @pytest.mark.anyio
    async def test_catalog_warmup_generates_only_one_token(self, monkeypatch):
        from app.core.config import settings
        from app.services.nlq.llm import client as client_module

        calls = []

        class StubClient:
            async def complete(self, **kwargs):
                calls.append(kwargs)
                return LLMResult(text="{}", model="m", provider="llamacpp")

        monkeypatch.setattr(settings, "nlq_llm_provider", "llamacpp")
        monkeypatch.setattr(client_module, "get_llm_client", lambda _provider: StubClient())

        await client_module.warm_catalog_prompt_cache()

        assert len(calls) == 1
        assert calls[0]["max_output_tokens"] == 1

    @pytest.mark.anyio
    async def test_cached_prompt_token_count_is_captured(self):
        def handler(_request):
            response = _ok('{"route":"refuse"}')
            body = json.loads(response.content)
            body["usage"]["prompt_tokens_details"] = {"cached_tokens": 9000}
            return httpx.Response(200, json=body)

        result = await _client(handler).complete(messages=[{"role": "user", "content": "hi"}])
        assert result.prompt_tokens == 10
        assert result.cached_prompt_tokens == 9000
        assert result.uncached_prompt_tokens == 10

    @pytest.mark.anyio
    async def test_purpose_prefix_and_uncached_usage_are_recorded(self):
        def handler(_request):
            response = _ok('{"route":"refuse"}')
            body = json.loads(response.content)
            body["usage"]["prompt_tokens"] = 100
            body["usage"]["prompt_tokens_details"] = {
                "cached_tokens": 70,
                "cache_creation_tokens": 20,
            }
            return httpx.Response(200, json=body)

        with collect_calls() as calls:
            result = await _client(handler).complete(
                messages=[{"role": "system", "content": "fixed"}],
                call_purpose="route",
                prompt_version="router-v1",
            )

        assert result.uncached_prompt_tokens == 30
        assert result.cache_write_prompt_tokens == 20
        assert result.prefix_hash
        assert len(calls) == 1
        assert calls[0].purpose == "route"
        assert calls[0].prompt_version == "router-v1"


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
        assert [message["role"] for message in seen["messages"]] == ["system", "user"]
        assert seen["messages"][0]["content"].startswith("Respond with a single JSON object")

    @pytest.mark.anyio
    async def test_system_context_and_schema_are_merged_in_stable_order(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok('{"route":"refuse"}')

        client = _client(handler, supports_json_schema=False, name="groq")
        await client.complete(
            messages=[
                {"role": "system", "content": "Primary instructions"},
                {"role": "system", "content": "Conversation checkpoint"},
                {"role": "user", "content": "hi"},
            ],
            json_schema=SCHEMA,
        )

        assert [message["role"] for message in seen["messages"]] == ["system", "user"]
        system = seen["messages"][0]["content"]
        assert system.index("Primary instructions") < system.index("Conversation checkpoint")
        assert system.index("Conversation checkpoint") < system.index("Respond with a single JSON")

    @pytest.mark.anyio
    async def test_native_schema_provider_still_coalesces_system_messages(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok('{"route":"refuse"}')

        client = _client(handler, supports_json_schema=True)
        await client.complete(
            messages=[
                {"role": "system", "content": "Primary instructions"},
                {"role": "user", "content": "earlier question"},
                {"role": "system", "content": "Session state"},
                {"role": "assistant", "content": "earlier answer"},
            ],
            json_schema=SCHEMA,
        )

        assert [message["role"] for message in seen["messages"]] == [
            "system", "user", "assistant",
        ]
        assert seen["messages"][0]["content"] == "Primary instructions\n\nSession state"

    @pytest.mark.anyio
    async def test_temperature_and_max_tokens_omitted_from_payload(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return _ok()

        await _client(handler).complete(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert "temperature" not in seen
        assert "max_tokens" not in seen
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

        with collect_calls() as recorded:
            with pytest.raises(LLMError):
                await _client(handler).complete(
                    messages=[{"role": "user", "content": "hi"}],
                    call_purpose="route",
                )
        assert calls["n"] == 1
        assert len(recorded) == 1
        assert recorded[0].finish_reason == "error"
        assert recorded[0].attempts == 1

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

    @pytest.mark.anyio
    async def test_llamacpp_reports_a_different_served_model_as_degraded(self):
        def handler(request):
            if request.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "actual-35b"}]})
            return httpx.Response(200)

        health = await _client(handler).health()

        assert health["status"] == "degraded"
        assert health["model"] == "m"
        assert health["served_models"] == ["actual-35b"]
        assert health["model_match"] is False


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
