from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec
from django.conf import settings

from tickfeeddmr.ai.services.llm._transport import one_line, open_stream
from tickfeeddmr.ai.services.llm.base import LLMProvider
from tickfeeddmr.ai.services.llm.exceptions import LLMResponseError
from tickfeeddmr.ai.services.llm.openai_compat.schemas import (
    Chunk,
    ToolCallAcc,
    ToolCallDelta,
    Usage,
)
from tickfeeddmr.ai.services.llm.resolve import provider_base_url
from tickfeeddmr.ai.services.llm.schemas import (
    TextDelta,
    ToolCallRequest,
    UsageReport,
)
from tickfeeddmr.ai.services.llm.sse import iter_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    import httpx

    from tickfeeddmr.ai.services.llm.schemas import (
        ChatMessage,
        ProviderChunk,
        ProviderSpec,
        ToolChoice,
        ToolSpec,
    )

_DONE = "[DONE]"


class OpenAICompatProvider(LLMProvider):
    """Адаптер OpenAI-совместимого `/chat/completions` (Groq, OpenRouter, Ollama)."""

    def __init__(
        self,
        *,
        spec: ProviderSpec,
        model_id: str,
        api_key: str | None,
        client: httpx.AsyncClient,
    ) -> None:
        self._url = f"{provider_base_url(spec)}/chat/completions"
        self._model_id = model_id
        self._api_key = api_key
        self._client = client

    async def aclose(self) -> None:
        await self._client.aclose()

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec],
        tool_choice: ToolChoice,
    ) -> AsyncIterator[ProviderChunk]:
        body = self._body(messages, tools, tool_choice)
        async with open_stream(
            self._client,
            self._url,
            body=body,
            headers=self._headers(),
        ) as resp:
            async for chunk in _read_stream(resp):
                yield chunk

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "text/event-stream"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _body(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        tool_choice: ToolChoice,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model_id,
            "messages": [_message_to_api(m) for m in messages],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": settings.AI_TEMPERATURE,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            body["tool_choice"] = tool_choice
        return body


def _message_to_api(message: ChatMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }
    if message.role == "assistant" and message.tool_calls:
        return {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments_json},
                }
                for call in message.tool_calls
            ],
        }
    return {"role": message.role, "content": message.content}


def _decode_chunk(data: str) -> Chunk:
    try:
        chunk = msgspec.json.decode(data, type=Chunk)
    except msgspec.DecodeError as exc:
        msg = f"Неразбираемый фрагмент ответа ИИ-провайдера: {one_line(data)}"
        raise LLMResponseError(msg) from exc
    if chunk.error is not None:
        msg = f"ИИ-провайдер прервал ответ: {one_line(chunk.error.message)}"
        raise LLMResponseError(msg)
    return chunk


def _accumulate_tool_calls(
    calls: dict[int, ToolCallAcc],
    deltas: list[ToolCallDelta],
) -> None:
    for position, tc in enumerate(deltas):
        # Gemini присылает вызовы без `index`.
        key = tc.index if tc.index is not None else position
        acc = calls.setdefault(key, ToolCallAcc())
        acc.id = acc.id or (tc.id or "")
        if tc.function is not None:
            acc.name = acc.name or (tc.function.name or "")
            if tc.function.arguments:
                acc.parts.append(tc.function.arguments)


async def _read_stream(resp: httpx.Response) -> AsyncIterator[ProviderChunk]:
    """Текст — сразу, вызовы инструментов и расход — после конца стрима."""
    calls: dict[int, ToolCallAcc] = {}
    usage: Usage | None = None
    async for data in iter_sse_data(resp):
        if data == _DONE:
            break
        chunk = _decode_chunk(data)
        if chunk.usage is not None:
            usage = chunk.usage
        for choice in chunk.choices:
            if choice.delta is None:
                continue
            if choice.delta.content:
                yield TextDelta(choice.delta.content)
            _accumulate_tool_calls(calls, choice.delta.tool_calls or [])

    for key in sorted(calls):
        acc = calls[key]
        yield ToolCallRequest(
            id=acc.id or f"call_{uuid4().hex[:12]}",
            name=acc.name,
            arguments_json="".join(acc.parts) or "{}",
        )
    if usage is not None:
        yield UsageReport(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
