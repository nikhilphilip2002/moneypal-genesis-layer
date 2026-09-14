"""Forward provisional answer text; the grounded answer event replaces it."""

from typing import Any


async def complete_answer(client, state: dict[str, Any], **kwargs):
    from app.services.workbench.graph import sse

    emit = state.get("emit")
    if emit is None:
        return await client.complete(**kwargs)

    async def on_text(text: str) -> None:
        await emit.put(sse("answer_delta", {"text": text}))

    await emit.put(sse("answer_reset", {}))
    try:
        result = await client.complete(**kwargs, on_text=on_text)
    except BaseException:
        await emit.put(sse("answer_reset", {}))
        raise
    if result.tool_calls:
        await emit.put(sse("answer_reset", {}))
    return result
