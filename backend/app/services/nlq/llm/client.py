"""Provider-agnostic LLM access for the NLQ pipeline.

Both targets speak the OpenAI chat-completions shape, so there is one HTTP implementation
and the providers differ only in base URL, auth, and how much of `response_format` they
honour. That difference is declared in `_ProviderProfile`, never branched on inside the
pipeline: no model-specific quirk is allowed to leak past this module.

- `llamacpp` — self-hosted `llama-server`. Supports `response_format: json_schema`, so the
  planner physically cannot emit malformed JSON.
- `groq` — already wired elsewhere in the codebase; carries development until the GPU node
  is procured. JSON *mode* only, so a parse-and-repair path is kept for it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class LLMError(RuntimeError):
    """Base for every failure that should degrade the ask bar rather than 500."""


class LLMTimeout(LLMError):
    pass


class LLMUnavailable(LLMError):
    """Provider unreachable, unauthenticated, or not configured."""


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0
    finish_reason: str = ""
    reasoning: str = ""
    """Whatever the server split out as chain of thought. Never parsed — kept only so an
    empty `text` can be diagnosed as "it thought instead of answering"."""

    def json(self) -> Any:
        """Parse the completion as JSON, tolerating the wrappers small models add.

        Under `json_schema` decoding this is a plain `json.loads`. The salvage path only
        matters for providers without grammar support.
        """
        if not self.text.strip():
            # A thinking model that runs out of budget mid-trace answers 200 OK with an
            # empty `content`. Saying so is the difference between a fixable report and
            # "the model did not return JSON: ''".
            raise LLMError(
                "model returned no content"
                + (f" (finish_reason={self.finish_reason})" if self.finish_reason else "")
                + (
                    f"; it spent the budget on {len(self.reasoning)} chars of reasoning — "
                    "disable thinking for this model (NLQ_LLM_THINKING=false) or raise "
                    "max_tokens"
                    if self.reasoning
                    else ""
                )
            )
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            pass
        stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", self.text.strip())
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"model did not return JSON (first 200 chars): {self.text[:200]!r}")


@runtime_checkable
class LLMClient(Protocol):
    provider: str
    model: str

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float | None = None,
    ) -> LLMResult: ...

    async def health(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class _ProviderProfile:
    name: str
    base_url: str
    api_key: str | None
    supports_json_schema: bool
    health_path: str
    health_method: str = "GET"
    chat_template_kwargs: dict[str, Any] | None = None
    """Extra arguments for the server-side chat template. llama.cpp uses these to switch a
    hybrid-reasoning model out of thinking mode; providers that do not know the field
    ignore it, so it is only sent where it is known to be honoured."""


@dataclass
class OpenAICompatibleClient:
    """One implementation for every OpenAI-shaped endpoint."""

    profile: _ProviderProfile
    model: str
    timeout_s: float = 30.0
    max_retries: int = 1
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    @property
    def provider(self) -> str:
        return self.profile.name

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.profile.api_key:
                headers["Authorization"] = f"Bearer {self.profile.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.profile.base_url.rstrip("/"),
                headers=headers,
                timeout=httpx.Timeout(self.timeout_s),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _response_format(self, json_schema: dict[str, Any] | None) -> dict[str, Any] | None:
        if json_schema is None:
            return None
        if self.profile.supports_json_schema:
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema.get("title", "response"),
                    "schema": json_schema,
                    "strict": True,
                },
            }
        # JSON mode only: the schema still shapes the output via the prompt, and
        # LLMResult.json() plus planner-side validation catch what slips through.
        return {"type": "json_object"}

    def _prepare_messages(
        self, messages: list[dict[str, str]], json_schema: dict[str, Any] | None
    ) -> list[dict[str, str]]:
        """Carry the schema in the prompt for providers without grammar support.

        Groq additionally *rejects* a json_object request whose messages never mention
        JSON, so this is required rather than merely helpful. It is appended rather than
        prepended so the cacheable system prefix stays byte-identical.
        """
        if json_schema is None or self.profile.supports_json_schema:
            return messages
        return [
            *messages,
            {
                "role": "system",
                "content": (
                    "Respond with a single JSON object and nothing else. It must conform "
                    "to this JSON schema:\n"
                    f"{json.dumps(json_schema, separators=(',', ':'))}"
                ),
            },
        ]

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float | None = None,
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._prepare_messages(messages, json_schema),
            "temperature": temperature,  # 0.0 — this is translation, not authorship
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self.profile.chat_template_kwargs:
            payload["chat_template_kwargs"] = dict(self.profile.chat_template_kwargs)
        response_format = self._response_format(json_schema)
        if response_format:
            payload["response_format"] = response_format

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = asyncio.get_event_loop().time()
            try:
                resp = await self._http().post(
                    "/chat/completions",
                    json=payload,
                    timeout=timeout_s or self.timeout_s,
                )
            except httpx.TimeoutException as exc:
                last_exc = LLMTimeout(f"{self.provider} timed out after {self.timeout_s}s")
                logger.warning("NLQ LLM timeout (attempt %d): %s", attempt + 1, exc)
                continue
            except httpx.HTTPError as exc:
                last_exc = LLMUnavailable(f"{self.provider} unreachable: {exc}")
                logger.warning("NLQ LLM transport error (attempt %d): %s", attempt + 1, exc)
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = LLMUnavailable(f"{self.provider} returned {resp.status_code}")
                logger.warning("NLQ LLM %s on attempt %d", resp.status_code, attempt + 1)
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                # 4xx is a request bug (bad schema, bad model name) — retrying repeats it.
                raise LLMError(f"{self.provider} rejected the request: {resp.text[:300]}")

            body = resp.json()
            choice = (body.get("choices") or [{}])[0]
            usage = body.get("usage") or {}
            message = choice.get("message") or {}
            return LLMResult(
                text=message.get("content") or "",
                reasoning=message.get("reasoning_content") or "",
                model=body.get("model", self.model),
                provider=self.provider,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
                finish_reason=choice.get("finish_reason", ""),
            )

        raise last_exc or LLMUnavailable(f"{self.provider} failed with no diagnosis")

    async def health(self) -> dict[str, Any]:
        """Never raises — the ask bar degrades on this, so it must always answer."""
        if self.profile.name == "groq" and not self.profile.api_key:
            return {"status": "unconfigured", "provider": self.provider, "model": self.model,
                    "detail": "GROQ_API_KEY is not set"}
        try:
            resp = await self._http().request(
                self.profile.health_method, self.profile.health_path, timeout=5.0
            )
        except httpx.HTTPError as exc:
            return {"status": "down", "provider": self.provider, "model": self.model,
                    "detail": str(exc)[:200]}
        ok = resp.status_code < 400
        return {
            "status": "ok" if ok else "degraded",
            "provider": self.provider,
            "model": self.model,
            "detail": "" if ok else f"HTTP {resp.status_code}",
        }


def _profile(provider: str) -> _ProviderProfile:
    if provider == "llamacpp":
        return _ProviderProfile(
            name="llamacpp",
            base_url=settings.nlq_llm_base_url,
            api_key=settings.nlq_llm_api_key,
            supports_json_schema=True,
            # llama-server exposes /health at the server root, one level above /v1.
            health_path=settings.nlq_llm_base_url.rstrip("/").removesuffix("/v1") + "/health",
            # Qwen3-class models think first and answer second. The plan is a form to fill
            # in, not a problem to reason about, and the trace costs the whole token budget
            # before a single character of JSON is emitted.
            chat_template_kwargs=None if settings.nlq_llm_thinking else {"enable_thinking": False},
        )
    if provider == "groq":
        return _ProviderProfile(
            name="groq",
            base_url=GROQ_BASE_URL,
            api_key=settings.groq_api_key,
            supports_json_schema=False,
            health_path="/models",
        )
    raise LLMUnavailable(
        f"NLQ_LLM_PROVIDER={provider!r} is not supported (expected 'llamacpp' or 'groq')"
    )


_cached: dict[str, OpenAICompatibleClient] = {}


def get_llm_client(provider: str | None = None) -> OpenAICompatibleClient:
    """Return the configured client. Cached so httpx keeps connections warm — and so the
    system prompt prefix hits llama.cpp's KV cache on every call."""
    name = (provider or settings.nlq_llm_provider or "groq").lower()
    if name not in _cached:
        profile = _profile(name)
        model = settings.groq_model if name == "groq" else settings.nlq_llm_model
        _cached[name] = OpenAICompatibleClient(
            profile=profile,
            model=model,
            timeout_s=settings.nlq_llm_timeout_s,
            max_retries=settings.nlq_llm_max_retries,
        )
    return _cached[name]
