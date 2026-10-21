from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import openai
from django.conf import settings
from openai import AsyncOpenAI

from tickfeeddmr.ai.services.llm.base import LLMProvider
from tickfeeddmr.ai.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
)
from tickfeeddmr.ai.services.llm.resolve import provider_base_url
from tickfeeddmr.ai.services.llm.schemas import (
    TextDelta,
    ToolCallRequest,
    UsageReport,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    import httpx2
    from openai.types.chat import (
        ChatCompletionFunctionToolParam,
        ChatCompletionMessageParam,
    )

    from tickfeeddmr.ai.services.llm.schemas import (
        ChatMessage,
        ProviderChunk,
        ProviderSpec,
        ToolChoice,
        ToolSpec,
    )

_KEYLESS_PLACEHOLDER = "unused"
_SERVER_ERROR_FROM = 500


class OpenAICompatProvider(LLMProvider):
    """Адаптер OpenAI-совместимого `/chat/completions` на SDK `openai`."""

    def __init__(
        self,
        *,
        spec: ProviderSpec,
        model_id: str,
        api_key: str | None,
        client: httpx2.AsyncClient,
    ) -> None:
        self._model_id = model_id
        self._sdk = AsyncOpenAI(
            base_url=provider_base_url(spec),
            api_key=api_key or _KEYLESS_PLACEHOLDER,
            http_client=client,
            max_retries=1,
        )

    async def aclose(self) -> None:
        await self._sdk.close()

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec],
        tool_choice: ToolChoice,
    ) -> AsyncIterator[ProviderChunk]:
        """Текст — сразу, вызовы инструментов и расход — после конца стрима.

        Фрагменты вызовов собирает сам SDK (`completions.stream`); итог берётся из
        `current_completion_snapshot`, а не `get_final_completion`, который
        бросает исключение на `finish_reason=length`.
        """
        try:
            async with self._sdk.chat.completions.stream(
                model=self._model_id,
                messages=cast(
                    "list[ChatCompletionMessageParam]",
                    [_message_to_api(m) for m in messages],
                ),
                stream_options={"include_usage": True},
                temperature=settings.AI_TEMPERATURE,
                tools=[_tool_to_api(t) for t in tools] if tools else openai.omit,
                tool_choice=tool_choice if tools else openai.omit,
            ) as stream:
                async for event in stream:
                    if event.type == "content.delta":
                        yield TextDelta(event.delta)
                snapshot = stream.current_completion_snapshot
        except openai.OpenAIError as exc:
            raise _map_error(exc) from exc
        except (TypeError, AssertionError) as exc:
            msg = "Неразбираемый ответ ИИ-провайдера"
            raise LLMResponseError(msg) from exc

        message = snapshot.choices[0].message if snapshot.choices else None
        for call in (message.tool_calls if message else None) or []:
            yield ToolCallRequest(
                id=call.id or f"call_{uuid4().hex[:12]}",
                name=call.function.name,
                arguments_json=call.function.arguments or "{}",
            )
        if snapshot.usage is not None:
            yield UsageReport(
                prompt_tokens=snapshot.usage.prompt_tokens,
                completion_tokens=snapshot.usage.completion_tokens,
            )


def _tool_to_api(tool: ToolSpec) -> ChatCompletionFunctionToolParam:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


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


def _map_error(exc: openai.OpenAIError) -> LLMError:
    """Ошибка слоя по исключению SDK; текст без тела ответа и заголовков."""
    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return LLMAuthError(
            f"ИИ-провайдер отклонил ключ доступа: HTTP {exc.status_code}",
        )
    if isinstance(exc, openai.APIStatusError):
        if (
            isinstance(exc, openai.RateLimitError)
            or exc.status_code >= _SERVER_ERROR_FROM
        ):
            return LLMConnectionError(
                f"ИИ-провайдер недоступен: HTTP {exc.status_code}",
            )
        return LLMResponseError(f"ИИ-провайдер вернул HTTP {exc.status_code}")
    if isinstance(exc, openai.APIConnectionError):
        return LLMConnectionError(
            f"Не удалось связаться с ИИ-провайдером: {type(exc).__name__}",
        )
    return LLMResponseError(f"Ошибка ответа ИИ-провайдера: {type(exc).__name__}")
