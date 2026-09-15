"""Forward provisional answer text; the grounded answer event replaces it."""

from typing import Any


async def complete_answer(
    client, state: dict[str, Any], *, trace_id: str | None = None, **kwargs
):
    from app.services.workbench.graph import sse

    emit = state.get("emit")
    if emit is None:
        return await client.complete(**kwargs)

    async def on_text(text: str) -> None:
        await emit.put(sse("answer_delta", {"text": text}))

    async def on_reasoning(text: str) -> None:
        if trace_id is not None:
            await emit.put(sse("trace_delta", {
                "id": trace_id, "reasoning_delta": text,
            }))

    async def on_tool_call(tool_call: dict[str, Any]) -> None:
        if trace_id is not None:
            await emit.put(sse("trace_delta", {
                "id": trace_id, "tool_call": tool_call,
            }))

    await emit.put(sse("answer_reset", {}))
    try:
        result = await client.complete(
            **kwargs,
            on_text=on_text,
            on_reasoning=on_reasoning,
            on_tool_call=on_tool_call,
        )
    except BaseException:
        await emit.put(sse("answer_reset", {}))
        raise
    if result.tool_calls:
        await emit.put(sse("answer_reset", {}))
    return result
