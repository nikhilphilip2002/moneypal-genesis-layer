from copy import deepcopy
from typing import Any

from app.services.nlq.llm.messages import ChatMessage
from app.services.workbench.agent_executor import shape_observation_text


def migrate_messages(turns: list[dict[str, Any]]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for turn in turns:
        turn["message_start"] = len(messages)
        messages.append({"role": "user", "content": turn.get("question", "")})
        tool_names = {}
        for event in turn.get("events", []):
            payload = event.get("payload", {})
            message = payload.get("message")
            if not isinstance(message, dict):
                continue
            if event.get("type") == "llm_assistant_message":
                messages.append(deepcopy(message))
                for call in message.get("tool_calls") or []:
                    tool_names[call["id"]] = call["function"]["name"]
            elif event.get("type") == "tool_result":
                tool = deepcopy(message)
                content = tool.get("content")
                if isinstance(content, str):
                    tool["content"] = shape_observation_text(
                        content,
                        tool_name=tool_names.get(tool.get("tool_call_id")),
                    )
                messages.append(tool)
        turn["message_end"] = len(messages)
    return messages
