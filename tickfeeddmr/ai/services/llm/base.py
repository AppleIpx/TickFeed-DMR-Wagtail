from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tickfeeddmr.ai.services.llm.schemas import (
        ChatMessage,
        ProviderChunk,
        ToolChoice,
        ToolSpec,
    )


class LLMProvider(ABC):
    """Общий интерфейс LLM-провайдера: стриминг ответа с вызовом инструментов."""

    @abstractmethod
    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec],
        tool_choice: ToolChoice,
    ) -> AsyncIterator[ProviderChunk]:
        """Отдать ответ модели на историю `messages` потоком фрагментов."""

    @abstractmethod
    async def aclose(self) -> None:
        """Закрыть HTTP-клиент провайдера."""
