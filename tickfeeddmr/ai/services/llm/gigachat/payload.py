from typing import TYPE_CHECKING, Any

import msgspec
from django.conf import settings

from tickfeeddmr.ai.services.llm.gigachat.json_schema import to_gigachat_parameters

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.ai.services.llm.schemas import ChatMessage, ToolChoice, ToolSpec

# В схеме GigaChat `temperature` строго больше нуля.
_MIN_TEMPERATURE = 0.0001


def _message_to_api(message: ChatMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {"role": "function", "name": message.name, "content": message.content}
    if message.role == "assistant" and message.tool_calls:
        call = message.tool_calls[0]
        try:
            arguments = msgspec.json.decode(call.arguments_json)
        except msgspec.DecodeError:
            arguments = {}
        return {
            "role": "assistant",
            "content": message.content,
            "function_call": {"name": call.name, "arguments": arguments},
        }
    return {"role": message.role, "content": message.content}


def build_payload(
    model_id: str,
    messages: Sequence[ChatMessage],
    tools: Sequence[ToolSpec],
    tool_choice: ToolChoice,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [_message_to_api(m) for m in messages],
        "temperature": max(settings.AI_TEMPERATURE, _MIN_TEMPERATURE),
    }
    if tools:
        payload["functions"] = [
            {
                "name": t.name,
                "description": t.description,
                "parameters": to_gigachat_parameters(t.parameters),
            }
            for t in tools
        ]
        payload["function_call"] = tool_choice
    return payload
