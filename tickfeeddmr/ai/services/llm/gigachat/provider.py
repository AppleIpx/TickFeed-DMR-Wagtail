import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec
from django.conf import settings

from tickfeeddmr.ai.services.llm.base import LLMProvider
from tickfeeddmr.ai.services.llm.exceptions import LLMError, LLMResponseError
from tickfeeddmr.ai.services.llm.gigachat.client import get_sdk_client
from tickfeeddmr.ai.services.llm.gigachat.errors import SDK_ERRORS, map_error
from tickfeeddmr.ai.services.llm.gigachat.payload import build_payload
from tickfeeddmr.ai.services.llm.resolve import provider_base_url
from tickfeeddmr.ai.services.llm.schemas import (
    TextDelta,
    ToolCallRequest,
    UsageReport,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tickfeeddmr.ai.services.llm.schemas import (
        ChatMessage,
        ProviderChunk,
        ProviderSpec,
        ToolChoice,
        ToolSpec,
    )

logger = logging.getLogger(__name__)


class GigaChatProvider(LLMProvider):
    """Адаптер GigaChat на SDK `gigachat` (протокол v1, `functions`)."""

    def __init__(
        self,
        *,
        spec: ProviderSpec,
        model_id: str,
        credentials: str,
    ) -> None:
        self._base_url = provider_base_url(spec)
        self._model_id = model_id
        self._credentials = credentials

    async def aclose(self) -> None:
        """Клиент SDK общий на процесс (хранит токен) и здесь не закрывается."""

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec],
        tool_choice: ToolChoice,
    ) -> AsyncIterator[ProviderChunk]:
        client = get_sdk_client(
            self._base_url,
            self._credentials,
            settings.GIGACHAT_SCOPE,
        )
        payload = build_payload(self._model_id, messages, tools, tool_choice)
        name = ""
        arguments: Any = None
        usage: tuple[int, int] | None = None
        try:
            async for chunk in client.astream(payload):
                if chunk.usage is not None:
                    usage = (chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
                for choice in chunk.choices:
                    delta = choice.delta
                    if delta.content:
                        yield TextDelta(delta.content)
                    call = delta.function_call
                    if call is not None and call.name:
                        name, arguments = call.name, call.arguments
                    _check_finish_reason(choice.finish_reason)
        except LLMError:
            raise
        except SDK_ERRORS as exc:
            raise map_error(exc) from exc

        if name:
            yield ToolCallRequest(
                id=f"gigachat_{uuid4().hex[:12]}",
                name=name,
                arguments_json=msgspec.json.encode(arguments or {}).decode(),
            )
        if usage is not None:
            yield UsageReport(prompt_tokens=usage[0], completion_tokens=usage[1])


def _check_finish_reason(reason: str | None) -> None:
    if reason == "error":
        msg = "GigaChat сгенерировал невалидные аргументы функции"
        raise LLMResponseError(msg)
    if reason == "blacklist":
        logger.warning("GigaChat ответил отказом по тематическим ограничениям")
