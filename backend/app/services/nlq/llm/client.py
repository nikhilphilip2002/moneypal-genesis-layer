"""OpenAI-compatible LLM access for the NLQ and Workbench pipelines.

There is one configured endpoint and one protocol. Deployment chooses the server through
``LLM_BASE_URL``, ``LLM_API_KEY`` and ``LLM_MODEL``; application code never routes prompts
between providers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)
from openai import AsyncStream
from openai.types.chat import ChatCompletionChunk

try:  # POSIX-only advisory locks; Windows development hosts fall back to the process gate.
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX platforms
    fcntl = None  # type: ignore[assignment]

from app.core.config import settings
from app.services.nlq.llm.messages import ChatMessage, coalesce_system_messages
from app.services.nlq.llm.context import (
    counting_payload,
    estimate_request_tokens,
    is_context_overflow,
)
from app.services.nlq.llm.telemetry import (
    CallKind,
    CallPurpose,
    CallRecord,
    record_call,
)

logger = logging.getLogger(__name__)

_request_gate_depth: ContextVar[int] = ContextVar(
    "llm_request_gate_depth", default=0
)


@asynccontextmanager
async def request_gate():
    """Serialize model work across both application containers.

    A normal asyncio lock only coordinates one process. The production API and PostgreSQL
    MCP containers share ``LOG_DIR``, so an advisory lock there also prevents their local
    model calls from occupying different llama-server slots concurrently. Acquisition is
    non-blocking to the event loop and cancellation always closes the descriptor.
    """
    depth = _request_gate_depth.get()
    if depth:
        token = _request_gate_depth.set(depth + 1)
        try:
            yield
        finally:
            _request_gate_depth.reset(token)
        return

    from app.services.nlq.ratelimit import llm_semaphore

    token = _request_gate_depth.set(1)
    try:
        if fcntl is None:
            # Without advisory file locks only this process is serialized. That is sufficient
            # for single-container development; production runs on Linux where the shared lock
            # below coordinates the API and MCP containers.
            _warn_no_file_lock()
            async with llm_semaphore():
                yield
            return

        async with llm_semaphore():
            path = settings.nlq_llm_lock_path
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            acquired = False
            try:
                while not acquired:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                    except BlockingIOError:
                        await asyncio.sleep(0.05)
                yield
            finally:
                if acquired:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
    finally:
        _request_gate_depth.reset(token)


_REASONING_FIELDS = ("reasoning_content", "reasoning")


def _strip_replay_reasoning(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Keep provider reasoning in stored history; replay it only when enabled."""
    if settings.nlq_llm_replay_reasoning:
        return list(messages)
    stripped: list[ChatMessage] = []
    for message in messages:
        if isinstance(message, dict) and any(
            key in message for key in _REASONING_FIELDS
        ):
            message = {
                k: v for k, v in message.items() if k not in _REASONING_FIELDS
            }
        stripped.append(message)
    return stripped


_NO_FILE_LOCK_WARNED = False


def _warn_no_file_lock() -> None:
    global _NO_FILE_LOCK_WARNED
    if not _NO_FILE_LOCK_WARNED:
        _NO_FILE_LOCK_WARNED = True
        logger.warning(
            "fcntl is unavailable; LLM requests are serialized per process only"
        )


class LLMError(RuntimeError):
    """Base for every failure that should degrade the ask bar rather than 500."""


class LLMTimeout(LLMError):
    pass


class LLMUnavailable(LLMError):
    """Provider unreachable, unauthenticated, or not configured."""


class LLMProtocolError(LLMError):
    """A successful provider response violated the native chat/tool protocol."""


class LLMIncomplete(LLMError):
    """The provider stopped before producing a complete response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMContextOverflow(LLMError):
    """The request or generation exceeded the provider's context capacity."""


class LLMResponseBlocked(LLMError):
    """The provider declined to return a response because of a content policy."""


_RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429})


def _retry_after_s(exc: APIStatusError) -> float | None:
    """Parse Retry-After as delta seconds or an HTTP date."""
    value = exc.response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def _validate_finish_reason(
    finish_reason: str,
    *,
    tool_calls: list[NativeToolCall],
    reasoning: str = "",
) -> None:
    if finish_reason == "length":
        detail = (
            f" after producing {len(reasoning)} chars of reasoning"
            if reasoning
            else ""
        )
        raise LLMIncomplete(
            f"model output was truncated at the configured token limit{detail}"
        )
    if finish_reason == "content_filter":
        raise LLMResponseBlocked(
            "model response was blocked by the provider content filter"
        )
    if finish_reason == "tool_calls" and not tool_calls:
        raise LLMProtocolError(
            "finish_reason was tool_calls but no tool calls were returned"
        )
    if finish_reason not in {"stop", "tool_calls"}:
        raise LLMProtocolError(f"unsupported finish_reason {finish_reason!r}")


async def _read_completion_stream(
    stream: AsyncStream[ChatCompletionChunk],
    on_text: Callable[[str], Awaitable[None]] | None = None,
    on_reasoning: Callable[[str], Awaitable[None]] | None = None,
    on_tool_call: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Assemble SDK chunks while forwarding public text and model activity."""
    message: dict[str, Any] = {"role": "assistant", "content": None}
    body: dict[str, Any] = {
        "choices": [{"message": message, "finish_reason": ""}]
    }
    calls: dict[int, dict[str, Any]] = {}
    finished = False
    async for event in stream:
        try:
            chunk = event.model_dump(exclude_none=True)
            if chunk.get("error"):
                if is_context_overflow(chunk["error"]):
                    raise LLMContextOverflow(
                        f"context window overflow: {chunk['error']}"
                    )
                raise LLMProtocolError(
                    f"completion stream error: {chunk['error']}"
                )
            if chunk.get("model"):
                body["model"] = chunk["model"]
            if chunk.get("usage"):
                body["usage"] = chunk["usage"]
            for choice in chunk.get("choices", []):
                if choice.get("index", 0) != 0:
                    continue
                delta = choice.get("delta") or {}
                for key in ("content", "reasoning_content", "reasoning"):
                    value = delta.get(key)
                    if value is not None:
                        if not isinstance(value, str):
                            raise LLMProtocolError(
                                f"delta.{key} must be a string"
                            )
                        message[key] = (message.get(key) or "") + value
                        if key == "content" and value and on_text:
                            await on_text(value)
                        elif (
                            key in _REASONING_FIELDS and value and on_reasoning
                        ):
                            await on_reasoning(value)
                for fragment in delta.get("tool_calls") or []:
                    index = fragment["index"]
                    if not isinstance(index, int) or index < 0:
                        raise LLMProtocolError(
                            "tool delta index must be a nonnegative integer"
                        )
                    call = calls.setdefault(
                        index,
                        {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if fragment.get("id"):
                        call["id"] += fragment["id"]
                    if fragment.get("type"):
                        call["type"] = fragment["type"]
                    for key in ("name", "arguments"):
                        call["function"][key] += (
                            fragment.get("function") or {}
                        ).get(key) or ""
                    if on_tool_call:
                        # Arguments are deliberately not forwarded while incomplete. They
                        # can contain outbound text which must pass the workbench privacy
                        # policy before it is rendered. The completed, sanitized arguments
                        # are emitted by the tool execution trace.
                        await on_tool_call(
                            {
                                "index": index,
                                "id": call["id"],
                                "name": call["function"]["name"],
                            }
                        )
                if choice.get("finish_reason"):
                    body["choices"][0]["finish_reason"] = choice[
                        "finish_reason"
                    ]
                    finished = True
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise LLMProtocolError("malformed completion stream") from exc
    if not finished:
        raise LLMProtocolError("completion stream was interrupted")
    if calls:
        message["tool_calls"] = [calls[index] for index in sorted(calls)]
    return body


@dataclass(frozen=True, slots=True)
class NativeToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0
    finish_reason: str = ""
    cache_write_prompt_tokens: int = 0
    uncached_prompt_tokens: int = 0
    attempts: int = 1
    retries: int = 0
    call_purpose: str = "unspecified"
    call_kind: str = "planned"
    prompt_version: str = ""
    catalog_version: str = ""
    prefix_hash: str = ""
    reasoning: str = ""
    """Whatever the server split out as chain of thought. Never parsed — kept only so an
    empty `text` can be diagnosed as "it thought instead of answering"."""
    tool_calls: list[NativeToolCall] = field(default_factory=list)
    assistant_message: ChatMessage | None = None

    def json(self) -> Any:
        """Parse the completion as JSON, tolerating the wrappers small models add.

        This method belongs only to legacy structured-output workflows. Native tools are
        parsed exclusively from ``message.tool_calls`` by ``complete()``; callers must never
        use this method to reconstruct a tool call from assistant content.

        Under `json_schema` decoding this is a plain `json.loads`. The salvage path matters
        only for separately supported providers without grammar support.
        """
        if not self.text.strip():
            # A thinking model that runs out of budget mid-trace answers 200 OK with an
            # empty `content`. Saying so is the difference between a fixable report and
            # "the model did not return JSON: ''".
            raise LLMError(
                "model returned no content"
                + (
                    f" (finish_reason={self.finish_reason})"
                    if self.finish_reason
                    else ""
                )
                + (
                    f"; it spent the budget on {len(self.reasoning)} chars of reasoning — "
                    "disable thinking for this model (NLQ_LLM_THINKING=false)"
                    if self.reasoning
                    else ""
                )
            )
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            pass
        stripped = re.sub(
            r"^\s*```(?:json)?\s*|\s*```\s*$", "", self.text.strip()
        )
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
        raise LLMError(
            f"model did not return JSON (first 200 chars): {self.text[:200]!r}"
        )


@runtime_checkable
class LLMClient(Protocol):
    provider: str
    model: str
    supports_native_tools: bool

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        json_schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        timeout_s: float | None = None,
        call_purpose: CallPurpose | str = "unspecified",
        call_kind: CallKind | str = "planned",
        prompt_version: str = "",
        catalog_version: str = "",
        prefix_hash: str = "",
        max_output_tokens: int | None = None,
        on_text: Callable[[str], Awaitable[None]] | None = None,
        on_reasoning: Callable[[str], Awaitable[None]] | None = None,
        on_tool_call: Callable[[dict[str, Any]], Awaitable[None]]
        | None = None,
    ) -> LLMResult: ...

    async def health(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class _ProviderProfile:
    name: str
    base_url: str
    api_key: str | None
    supports_json_schema: bool
    supports_native_tools: bool


def _native_tool_names(tools: list[dict[str, Any]]) -> set[str]:
    """Validate the outbound native tool envelope and return its function names."""
    if not tools:
        raise LLMError("native tool mode requires at least one tool")

    names: set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            raise LLMError(f"invalid native tool definition at index {index}")
        function = tool.get("function")
        name = function.get("name") if isinstance(function, dict) else None
        if (
            tool.get("type") != "function"
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise LLMError(f"invalid native tool definition at index {index}")
        if name in names:
            raise LLMError(f"duplicate native tool definition {name!r}")
        names.add(name)
    return names


def _choice_tool_names(
    tool_choice: str | dict[str, Any] | None,
    offered_names: set[str],
) -> set[str]:
    """Validate an allowed_tools choice and constrain accepted provider tool calls."""
    if tool_choice == "none":
        return set()
    if (
        not isinstance(tool_choice, dict)
        or tool_choice.get("type") != "allowed_tools"
    ):
        return offered_names
    allowed = tool_choice.get("allowed_tools")
    if not isinstance(allowed, dict) or allowed.get("mode") not in {
        "auto",
        "required",
    }:
        raise LLMError("allowed_tools requires an auto or required mode")
    entries = allowed.get("tools")
    if not isinstance(entries, list) or not entries:
        raise LLMError("allowed_tools requires a nonempty function list")
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise LLMError(
                "allowed_tools contains an invalid function reference"
            )
        function = entry.get("function") if isinstance(entry, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if entry.get("type") != "function" or not isinstance(name, str):
            raise LLMError(
                "allowed_tools contains an invalid function reference"
            )
        if name not in offered_names or name in names:
            raise LLMError(
                f"allowed_tools contains an unknown or duplicate function {name!r}"
            )
        names.add(name)
    return names


def _parse_native_tool_calls(
    message: dict[str, Any],
    *,
    allowed_names: set[str],
) -> list[NativeToolCall]:
    raw_calls = message.get("tool_calls")
    if raw_calls is None:
        return []
    if not isinstance(raw_calls, list):
        raise LLMProtocolError("message.tool_calls must be an array")

    parsed: list[NativeToolCall] = []
    seen_ids: set[str] = set()
    for index, raw_call in enumerate(raw_calls):
        if not isinstance(raw_call, dict):
            raise LLMProtocolError(
                f"tool call at index {index} must be an object"
            )
        call_id = raw_call.get("id")
        if not isinstance(call_id, str) or not call_id.strip():
            raise LLMProtocolError(
                f"tool call at index {index} has no call ID"
            )
        if call_id in seen_ids:
            raise LLMProtocolError(f"duplicate tool call ID {call_id!r}")
        seen_ids.add(call_id)
        if raw_call.get("type") != "function":
            raise LLMProtocolError(
                f"tool call {call_id!r} is not type 'function'"
            )

        function = raw_call.get("function")
        if not isinstance(function, dict):
            raise LLMProtocolError(
                f"tool call {call_id!r} has no function object"
            )
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise LLMProtocolError(
                f"tool call {call_id!r} has no function name"
            )
        if name not in allowed_names:
            raise LLMProtocolError(
                f"tool call {call_id!r} names unknown function {name!r}"
            )

        raw_arguments = function.get("arguments")
        if not isinstance(raw_arguments, str):
            raise LLMProtocolError(
                f"tool call {call_id!r} arguments must be a JSON-encoded string"
            )
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise LLMProtocolError(
                f"tool call {call_id!r} arguments are not valid JSON"
            ) from exc
        if not isinstance(arguments, dict):
            raise LLMProtocolError(
                f"tool call {call_id!r} arguments must decode to an object"
            )
        parsed.append(
            NativeToolCall(id=call_id, name=name, arguments=arguments)
        )
    return parsed


@dataclass
class OpenAICompatibleClient:
    """One implementation for every OpenAI-shaped endpoint."""

    profile: _ProviderProfile
    model: str
    timeout_s: float = 30.0
    max_retries: int = 4
    transport_max_retries: int = 1
    retry_base_delay_s: float = 2.0
    retry_max_delay_s: float = 30.0
    retry_budget_s: float = 30.0
    _client: AsyncOpenAI | None = field(default=None, repr=False)
    _context_metadata: dict[str, Any] = field(default_factory=dict, repr=False)
    _metadata_checked_at: float = field(default=0.0, repr=False)
    _count_unavailable_until: float = field(default=0.0, repr=False)
    _token_count_scale: float = field(default=1.0, repr=False)

    async def context_window(self) -> int:
        if (
            not self._metadata_checked_at
            or time.monotonic() - self._metadata_checked_at > 60
        ):
            try:
                models = await self._openai().models.list(timeout=5.0)
                model = next(
                    (item for item in models.data if item.id == self.model),
                    None,
                )
                if model is None and len(models.data) == 1:
                    model = models.data[0]
                if model is not None:
                    metadata = model.model_dump().get("meta")
                    self._context_metadata = (
                        metadata if isinstance(metadata, dict) else {}
                    )
                else:
                    self._context_metadata = {}
            except (APIError, httpx.HTTPError):
                logger.warning(
                    "Model context metadata unavailable; using configured limit"
                )
            self._metadata_checked_at = time.monotonic()
        runtime_context = self._context_metadata.get("n_ctx")
        if type(runtime_context) is int and runtime_context > 0:
            return runtime_context
        return max(1, settings.workbench_context_window)

    async def count_input_tokens(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> int:
        prepared = self._prepare_messages(messages, None)
        tokens = estimate_request_tokens(prepared, tools)
        if time.monotonic() >= self._count_unavailable_until:
            try:
                body = counting_payload(self.model, prepared, tools)
                counted = await self._openai().post(
                    "messages/count_tokens",
                    body=body,
                    cast_to=dict[str, Any],
                    options={"timeout": 5.0},
                )
                value = counted.get("input_tokens")
                if not isinstance(value, int) or value <= 0:
                    raise ValueError("invalid input_tokens")
                tokens = value
            except (
                APIError,
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
            ):
                self._count_unavailable_until = time.monotonic() + 60
                logger.warning(
                    "Token counting unavailable; using conservative request estimate"
                )
        return max(1, int(tokens * self._token_count_scale + 0.999))

    def observe_input_tokens(self, counted: int, actual: int) -> None:
        if counted > 0 and actual > counted:
            self._token_count_scale *= actual / counted

    @property
    def provider(self) -> str:
        return self.profile.name

    @property
    def supports_native_tools(self) -> bool:
        return self.profile.supports_native_tools

    def _openai(self) -> AsyncOpenAI:
        if self._client is None or self._client.is_closed():
            self._client = AsyncOpenAI(
                api_key=self.profile.api_key or "not-needed",
                base_url=self.profile.base_url.rstrip("/") + "/",
                timeout=self.timeout_s,
                # This class owns retries so attempt telemetry remains exact.
                max_retries=0,
            )
            # Resolve this synchronously once. The SDK otherwise starts a worker thread
            # on the first async request solely to populate its diagnostic OS header.
            system = platform.system().lower()
            self._client._platform = {
                "darwin": "MacOS",
                "linux": "Linux",
                "windows": "Windows",
                "freebsd": "FreeBSD",
                "openbsd": "OpenBSD",
            }.get(system, "Unknown")
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed():
            await self._client.close()

    async def _wait_before_retry(
        self,
        attempt: int,
        retry_deadline: float,
        status_error: APIStatusError | None = None,
    ) -> bool:
        remaining = retry_deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return False
        retry_after = (
            _retry_after_s(status_error) if status_error is not None else None
        )
        delay = (
            retry_after
            if retry_after is not None
            else self.retry_base_delay_s * (2**attempt)
        )
        await asyncio.sleep(
            min(remaining, self.retry_max_delay_s, max(0.0, delay))
        )
        return True

    def _response_format(
        self, json_schema: dict[str, Any] | None
    ) -> dict[str, Any] | None:
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
        self, messages: list[ChatMessage], json_schema: dict[str, Any] | None
    ) -> list[ChatMessage]:
        """Normalize system context and carry schemas for JSON-mode-only test profiles."""
        prepared = coalesce_system_messages(_strip_replay_reasoning(messages))
        if json_schema is None or self.profile.supports_json_schema:
            return prepared
        return coalesce_system_messages(
            [
                *prepared,
                {
                    "role": "system",
                    "content": (
                        "Respond with a single JSON object and nothing else. It must conform "
                        "to this JSON schema:\n"
                        f"{json.dumps(json_schema, separators=(',', ':'))}"
                    ),
                },
            ]
        )

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        json_schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        timeout_s: float | None = None,
        call_purpose: CallPurpose | str = "unspecified",
        call_kind: CallKind | str = "planned",
        prompt_version: str = "",
        catalog_version: str = "",
        prefix_hash: str = "",
        max_output_tokens: int | None = None,
        on_text: Callable[[str], Awaitable[None]] | None = None,
        on_reasoning: Callable[[str], Awaitable[None]] | None = None,
        on_tool_call: Callable[[dict[str, Any]], Awaitable[None]]
        | None = None,
    ) -> LLMResult:
        if tools is not None and json_schema is not None:
            raise LLMError(
                "tools and json_schema are mutually exclusive request modes"
            )
        if tools is None and (
            tool_choice is not None or parallel_tool_calls is not None
        ):
            raise LLMError("tool_choice and parallel_tool_calls require tools")
        allowed_tool_names: set[str] = set()
        if tools is not None:
            if not self.profile.supports_native_tools:
                raise LLMError(
                    f"{self.provider} does not support native tools"
                )
            allowed_tool_names = _choice_tool_names(
                tool_choice, _native_tool_names(tools)
            )

        request_started = asyncio.get_event_loop().time()
        prepared_messages = self._prepare_messages(messages, json_schema)
        effective_prefix_hash = prefix_hash
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": prepared_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max(1, int(max_output_tokens))
        response_format = self._response_format(json_schema)
        if response_format:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
            if parallel_tool_calls is not None:
                payload["parallel_tool_calls"] = parallel_tool_calls

        last_exc: Exception | None = None
        attempts_run = 0
        effective_timeout_s = (
            timeout_s if timeout_s is not None else self.timeout_s
        )
        retry_deadline = request_started + self.retry_budget_s
        successful_response: tuple[dict[str, Any], int] | None = None
        visible_output_emitted = False

        async def emit_text(text: str) -> None:
            nonlocal visible_output_emitted
            if on_text is not None:
                visible_output_emitted = True
                await on_text(text)

        async def emit_reasoning(text: str) -> None:
            nonlocal visible_output_emitted
            if on_reasoning is not None:
                visible_output_emitted = True
                await on_reasoning(text)

        async def emit_tool_call(tool_call: dict[str, Any]) -> None:
            nonlocal visible_output_emitted
            if on_tool_call is not None:
                visible_output_emitted = True
                await on_tool_call(tool_call)

        async with request_gate():
            for attempt in range(self.max_retries + 1):
                attempts_run = attempt + 1
                try:
                    stream = await self._openai().chat.completions.create(
                        **payload,
                        timeout=effective_timeout_s,
                    )
                    try:
                        body = await _read_completion_stream(
                            stream,
                            on_text=emit_text,
                            on_reasoning=emit_reasoning,
                            on_tool_call=emit_tool_call,
                        )
                    except (
                        APIError,
                        ValueError,
                        TypeError,
                        KeyError,
                        AttributeError,
                    ) as exc:
                        if is_context_overflow(exc):
                            raise LLMContextOverflow(
                                "context window overflow during generation"
                            ) from exc
                        raise LLMProtocolError(
                            "malformed completion stream"
                        ) from exc
                    finally:
                        await stream.close()
                except asyncio.CancelledError:
                    logger.info(
                        "LLM request cancelled: purpose=%s provider=%s attempt=%s",
                        call_purpose,
                        self.provider,
                        attempt + 1,
                    )
                    raise
                except LLMProtocolError as exc:
                    last_exc = exc
                    break
                except LLMContextOverflow as exc:
                    last_exc = exc
                    break
                except (APITimeoutError, httpx.TimeoutException) as exc:
                    last_exc = LLMTimeout(
                        f"{self.provider} timed out after {effective_timeout_s}s"
                    )
                    logger.warning(
                        "NLQ LLM timeout (attempt %d): %s", attempt + 1, exc
                    )
                    if (
                        visible_output_emitted
                        or attempt
                        >= min(self.max_retries, self.transport_max_retries)
                        or not await self._wait_before_retry(
                            attempt, retry_deadline
                        )
                    ):
                        break
                    continue
                except APIStatusError as exc:
                    if is_context_overflow(exc):
                        last_exc = LLMContextOverflow(
                            f"context window overflow: {str(exc)[:500]}"
                        )
                        break
                    if (
                        exc.status_code in _RETRYABLE_STATUS_CODES
                        or exc.status_code >= 500
                    ):
                        last_exc = LLMUnavailable(
                            f"{self.provider} returned retryable HTTP {exc.status_code}: "
                            f"{str(exc)[:200]}"
                        )
                        logger.warning(
                            "NLQ LLM %s on attempt %d",
                            exc.status_code,
                            attempt + 1,
                        )
                        if (
                            attempt >= self.max_retries
                            or not await self._wait_before_retry(
                                attempt, retry_deadline, exc
                            )
                        ):
                            break
                        continue
                    last_exc = LLMError(
                        f"{self.provider} rejected the request: {str(exc)[:300]}"
                    )
                    break
                except (APIConnectionError, httpx.HTTPError) as exc:
                    last_exc = LLMUnavailable(
                        f"{self.provider} unreachable: {exc}"
                    )
                    logger.warning(
                        "NLQ LLM transport error (attempt %d): %s",
                        attempt + 1,
                        exc,
                    )
                    if (
                        visible_output_emitted
                        or attempt
                        >= min(self.max_retries, self.transport_max_retries)
                        or not await self._wait_before_retry(
                            attempt, retry_deadline
                        )
                    ):
                        break
                    continue

                successful_response = (body, attempt)
                break

        if successful_response is not None:
            body, successful_attempt = successful_response
            choice = (body.get("choices") or [{}])[0]
            usage = body.get("usage") or {}
            prompt_details = usage.get("prompt_tokens_details") or {}
            cache_write_tokens = int(
                prompt_details.get("cache_write_tokens")
                or prompt_details.get("cache_creation_tokens")
                or usage.get("cache_write_tokens")
                or usage.get("cache_creation_input_tokens")
                or 0
            )
            prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            cached_prompt_tokens = int(
                prompt_details.get("cached_tokens", 0) or 0
            )
            message = choice.get("message") or {}
            finish_reason = choice.get("finish_reason", "")
            try:
                if not isinstance(message, dict):
                    raise LLMProtocolError("choice.message must be an object")
                if not isinstance(finish_reason, str) or not finish_reason:
                    raise LLMProtocolError(
                        "choice.finish_reason must be a nonempty string"
                    )
                if finish_reason in {"length", "content_filter"}:
                    _validate_finish_reason(
                        finish_reason,
                        tool_calls=[],
                        reasoning=str(
                            message.get("reasoning_content")
                            or message.get("reasoning")
                            or ""
                        ),
                    )
                tool_calls = _parse_native_tool_calls(
                    message,
                    allowed_names=allowed_tool_names,
                )
                content = message.get("content")
                if content is not None and not isinstance(content, str):
                    raise LLMProtocolError(
                        "message.content must be a string or null"
                    )
                reasoning = str(
                    message.get("reasoning_content")
                    or message.get("reasoning")
                    or ""
                )
                _validate_finish_reason(
                    finish_reason,
                    tool_calls=tool_calls,
                    reasoning=reasoning,
                )
            except (
                LLMProtocolError,
                LLMIncomplete,
                LLMResponseBlocked,
            ) as exc:
                if isinstance(exc, LLMIncomplete):
                    exc.prompt_tokens = prompt_tokens
                    exc.completion_tokens = int(
                        usage.get("completion_tokens", 0) or 0
                    )
                duration_ms = int(
                    (asyncio.get_event_loop().time() - request_started) * 1000
                )
                recorded_finish_reason = (
                    finish_reason
                    if isinstance(exc, (LLMIncomplete, LLMResponseBlocked))
                    else "protocol_error"
                )
                record_call(
                    CallRecord(
                        purpose=str(call_purpose),
                        call_kind=str(call_kind),
                        provider=self.provider,
                        model=str(body.get("model", self.model)),
                        prompt_version=prompt_version,
                        catalog_version=catalog_version,
                        prefix_hash=effective_prefix_hash,
                        prompt_tokens=prompt_tokens,
                        cached_prompt_tokens=cached_prompt_tokens,
                        cache_write_prompt_tokens=cache_write_tokens,
                        uncached_prompt_tokens=(
                            prompt_tokens - cached_prompt_tokens
                            if cached_prompt_tokens <= prompt_tokens
                            else prompt_tokens
                        ),
                        completion_tokens=int(
                            usage.get("completion_tokens", 0) or 0
                        ),
                        duration_ms=duration_ms,
                        attempts=successful_attempt + 1,
                        retries=successful_attempt,
                        finish_reason=recorded_finish_reason,
                    )
                )
                logger.warning(
                    "LLM completion rejected purpose=%s provider=%s model=%s "
                    "finish_reason=%s: %s",
                    call_purpose,
                    self.provider,
                    body.get("model", self.model),
                    recorded_finish_reason,
                    exc,
                )
                from app.core.logging import log_raw_trace

                log_raw_trace(
                    f"LLM completion rejected: {exc}",
                    event=(
                        "llm_protocol_error"
                        if isinstance(exc, LLMProtocolError)
                        else "llm_finish_error"
                    ),
                    provider=self.provider,
                    model=body.get("model", self.model),
                    raw_payload=payload,
                    raw_response=body,
                    duration_ms=duration_ms,
                    status_code=200,
                    call_purpose=str(call_purpose),
                    call_kind=str(call_kind),
                    finish_reason=recorded_finish_reason,
                    error=str(exc),
                    level=logging.WARNING,
                )
                raise
            assistant_message: ChatMessage = {
                "role": "assistant",
                "content": content,
            }
            if reasoning:
                assistant_message["reasoning_content"] = reasoning
            if message.get("tool_calls") is not None:
                assistant_message["tool_calls"] = list(message["tool_calls"])
            result = LLMResult(
                text=content or "",
                reasoning=reasoning,
                tool_calls=tool_calls,
                assistant_message=assistant_message,
                model=body.get("model", self.model),
                provider=self.provider,
                prompt_tokens=prompt_tokens,
                cached_prompt_tokens=cached_prompt_tokens,
                cache_write_prompt_tokens=cache_write_tokens,
                # OpenAI includes cached tokens inside prompt_tokens; some llama.cpp
                # builds report only newly evaluated prompt tokens alongside a larger
                # cached count. Preserve the provider's uncached value in that shape.
                uncached_prompt_tokens=(
                    prompt_tokens - cached_prompt_tokens
                    if cached_prompt_tokens <= prompt_tokens
                    else prompt_tokens
                ),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                duration_ms=int(
                    (asyncio.get_event_loop().time() - request_started) * 1000
                ),
                finish_reason=finish_reason,
                attempts=successful_attempt + 1,
                retries=successful_attempt,
                call_purpose=str(call_purpose),
                call_kind=str(call_kind),
                prompt_version=prompt_version,
                catalog_version=catalog_version,
                prefix_hash=effective_prefix_hash,
            )
            logger.info(
                "LLM completion purpose=%s kind=%s provider=%s model=%s prompt_tokens=%s "
                "cached_prompt_tokens=%s cache_write_prompt_tokens=%s uncached_prompt_tokens=%s "
                "completion_tokens=%s finish_reason=%s tool_calls=%s tool_names=%s "
                "duration_ms=%s retries=%s prefix=%s",
                result.call_purpose,
                result.call_kind,
                result.provider,
                result.model,
                result.prompt_tokens,
                result.cached_prompt_tokens,
                result.cache_write_prompt_tokens,
                result.uncached_prompt_tokens,
                result.completion_tokens,
                result.finish_reason,
                len(result.tool_calls),
                [call.name for call in result.tool_calls],
                result.duration_ms,
                result.retries,
                result.prefix_hash,
            )
            from app.core.logging import log_raw_trace

            log_raw_trace(
                "LLM completion received",
                event="llm_completion",
                provider=result.provider,
                model=result.model,
                prompt=payload.get("messages"),
                completion=result.text,
                raw_payload=payload,
                raw_response=body,
                duration_ms=result.duration_ms,
                status_code=200,
                finish_reason=result.finish_reason,
                tool_call_count=len(result.tool_calls),
                tool_names=tuple(call.name for call in result.tool_calls),
                call_purpose=result.call_purpose,
                call_kind=result.call_kind,
                prompt_version=result.prompt_version,
                catalog_version=result.catalog_version,
                prefix_hash=result.prefix_hash,
                attempts=result.attempts,
                retries=result.retries,
                usage={
                    "prompt_tokens": result.prompt_tokens,
                    "cached_prompt_tokens": result.cached_prompt_tokens,
                    "cache_write_prompt_tokens": result.cache_write_prompt_tokens,
                    "uncached_prompt_tokens": result.uncached_prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.prompt_tokens
                    + result.completion_tokens,
                },
            )
            record_call(
                CallRecord(
                    purpose=result.call_purpose,
                    call_kind=result.call_kind,
                    provider=result.provider,
                    model=result.model,
                    prompt_version=result.prompt_version,
                    catalog_version=result.catalog_version,
                    prefix_hash=result.prefix_hash,
                    prompt_tokens=result.prompt_tokens,
                    cached_prompt_tokens=result.cached_prompt_tokens,
                    cache_write_prompt_tokens=result.cache_write_prompt_tokens,
                    uncached_prompt_tokens=result.uncached_prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    duration_ms=result.duration_ms,
                    attempts=result.attempts,
                    retries=result.retries,
                    finish_reason=result.finish_reason,
                    tool_call_count=len(result.tool_calls),
                    tool_names=tuple(call.name for call in result.tool_calls),
                )
            )
            return result
        from app.core.logging import log_raw_trace

        failed_attempts = attempts_run
        failed_duration_ms = int(
            (asyncio.get_event_loop().time() - request_started) * 1000
        )
        record_call(
            CallRecord(
                purpose=str(call_purpose),
                call_kind=str(call_kind),
                provider=self.provider,
                model=self.model,
                prompt_version=prompt_version,
                catalog_version=catalog_version,
                prefix_hash=effective_prefix_hash,
                prompt_tokens=0,
                cached_prompt_tokens=0,
                cache_write_prompt_tokens=0,
                uncached_prompt_tokens=0,
                completion_tokens=0,
                duration_ms=failed_duration_ms,
                attempts=failed_attempts,
                retries=max(0, failed_attempts - 1),
                finish_reason="error",
            )
        )
        log_raw_trace(
            f"LLM request failed: {last_exc}",
            event="llm_error",
            provider=self.provider,
            model=self.model,
            call_purpose=str(call_purpose),
            call_kind=str(call_kind),
            prompt_version=prompt_version,
            catalog_version=catalog_version,
            prefix_hash=effective_prefix_hash,
            duration_ms=failed_duration_ms,
            attempts=failed_attempts,
            retries=max(0, failed_attempts - 1),
            raw_payload=payload,
            error=str(last_exc),
            level=logging.WARNING,
        )
        raise last_exc or LLMUnavailable(
            f"{self.provider} failed with no diagnosis"
        )

    async def health(self) -> dict[str, Any]:
        """Return endpoint readiness from the standard OpenAI models endpoint."""
        try:
            models = await self._openai().models.list(timeout=5.0)
        except APIStatusError as exc:
            return {
                "status": "degraded",
                "provider": self.provider,
                "model": self.model,
                "detail": f"HTTP {exc.status_code}",
                "served_models": [],
                "model_match": False,
            }
        except (APIConnectionError, APITimeoutError) as exc:
            return {
                "status": "down",
                "provider": self.provider,
                "model": self.model,
                "detail": str(exc)[:200],
            }
        served_models = [str(item.id) for item in models.data if item.id]
        model_match = not served_models or self.model in served_models
        return {
            "status": "ok" if model_match else "degraded",
            "provider": self.provider,
            "model": self.model,
            "detail": (
                ""
                if model_match
                else f"Configured model {self.model!r} is not served"
            ),
            "served_models": served_models,
            "model_match": model_match,
        }


def _profile() -> _ProviderProfile:
    return _ProviderProfile(
        name="llm",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        supports_json_schema=True,
        supports_native_tools=True,
    )


_cached: OpenAICompatibleClient | None = None


def get_llm_client() -> OpenAICompatibleClient:
    """Return the sole configured client, cached to keep HTTP connections warm."""
    global _cached
    if _cached is None:
        _cached = OpenAICompatibleClient(
            profile=_profile(),
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.nlq_llm_max_retries,
        )
    return _cached
