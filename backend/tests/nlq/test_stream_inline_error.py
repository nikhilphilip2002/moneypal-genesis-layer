"""A provider may report a transient failure inside an HTTP 200 stream body."""

from __future__ import annotations

import pytest

from app.services.nlq.llm.client import (
    LLMProtocolError,
    LLMUnavailable,
    _read_completion_stream,
    _stream_error_code,
)


class _FakeEvent:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self, **_kwargs) -> dict:
        return self._payload


class _FakeStream:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads

    def __aiter__(self):
        async def gen():
            for payload in self._payloads:
                yield _FakeEvent(payload)

        return gen()

    async def close(self) -> None:
        return None


@pytest.mark.anyio
async def test_stream_error_code_reads_int_and_string_forms():
    assert _stream_error_code({"code": 503}) == 503
    assert _stream_error_code({"status": "500"}) == 500
    assert _stream_error_code({"message": "no code here"}) is None
    assert _stream_error_code("plain text") is None


@pytest.mark.anyio
async def test_inline_5xx_stream_error_is_unavailable_not_protocol():
    """NVIDIA NIM cold-starts answer HTTP 200 with a 503 inlined in the body."""
    stream = _FakeStream([{"error": {"code": 503, "message": "Service temporarily overloaded"}}])
    with pytest.raises(LLMUnavailable) as excinfo:
        await _read_completion_stream(stream)
    assert "503" in str(excinfo.value)


@pytest.mark.anyio
async def test_inline_non_5xx_stream_error_stays_protocol_error():
    stream = _FakeStream([{"error": {"code": 400, "message": "bad request"}}])
    with pytest.raises(LLMProtocolError):
        await _read_completion_stream(stream)
