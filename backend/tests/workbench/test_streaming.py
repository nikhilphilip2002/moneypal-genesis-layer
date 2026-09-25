import asyncio
import json

import pytest

from app.services.nlq.llm.client import LLMResult, LLMTimeout, NativeToolCall
from app.services.workbench.streaming import complete_answer


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["answer", "tools", "error", "cancel"])
async def test_answer_deltas_are_live_and_never_retracted(outcome):
    queue = asyncio.Queue()

    class Client:
        async def complete(self, *, on_text, on_reasoning, on_tool_call):
            assert "answer_start" in queue.get_nowait()
            await on_reasoning("Checking facts")
            frame = queue.get_nowait()
            assert frame.startswith("event: trace_delta\n")
            assert json.loads(frame.split("data: ")[1]) == {
                "id": "model-1",
                "reasoning_delta": "Checking facts",
            }
            await on_tool_call({"index": 0, "id": "a", "name": "tool"})
            frame = queue.get_nowait()
            assert frame.startswith("event: trace_delta\n")
            assert json.loads(frame.split("data: ")[1]) == {
                "id": "model-1",
                "tool_call": {"index": 0, "id": "a", "name": "tool"},
            }
            await on_text("Hello")
            frame = queue.get_nowait()
            assert frame.startswith("event: answer_delta\n")
            assert json.loads(frame.split("data: ")[1]) == {"text": "Hello"}
            if outcome == "error":
                raise LLMTimeout("timeout")
            if outcome == "cancel":
                raise asyncio.CancelledError()
            return LLMResult(
                text="Hello",
                model="m",
                provider="llm",
                tool_calls=[NativeToolCall("a", "tool", {})]
                if outcome == "tools"
                else [],
            )

    if outcome in {"error", "cancel"}:
        with pytest.raises(
            LLMTimeout if outcome == "error" else asyncio.CancelledError
        ):
            await complete_answer(
                Client(), {"emit": queue}, trace_id="model-1"
            )
    else:
        result = await complete_answer(
            Client(), {"emit": queue}, trace_id="model-1"
        )
        assert result.text == "Hello"
    assert queue.empty()
