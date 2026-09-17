"""Forward model content without assigning provisional or final semantics to it."""

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

    # A model response is a permanent message, even when it also contains a native tool
    # call. The client reports the boundary so the UI can preserve separate messages; it
    # never clears or reclassifies content after seeing how the response finishes.
    await emit.put(sse("answer_start", {}))
    return await client.complete(
        **kwargs,
        on_text=on_text,
        on_reasoning=on_reasoning,
        on_tool_call=on_tool_call,
    )
