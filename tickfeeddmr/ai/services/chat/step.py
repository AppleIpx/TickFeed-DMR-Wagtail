from contextlib import aclosing
from typing import TYPE_CHECKING

import msgspec

from tickfeeddmr.ai.services.chat.deadline import next_before
from tickfeeddmr.ai.services.chat.events import TextDeltaEvent
from tickfeeddmr.ai.services.llm.schemas import (
    TextDelta,
    ToolCallRequest,
    UsageReport,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tickfeeddmr.ai.services.llm.base import LLMProvider
    from tickfeeddmr.ai.services.llm.schemas import ChatMessage, ToolSpec


class StepResult(msgspec.Struct, frozen=True):
    """Что модель ответила на одном шаге цикла."""

    text: str
    calls: tuple[ToolCallRequest, ...]
    usage: UsageReport | None


async def stream_step(
    provider: LLMProvider,
    messages: Sequence[ChatMessage],
    specs: Sequence[ToolSpec],
    *,
    final: bool,
    deadline: float,
) -> AsyncIterator[TextDeltaEvent | StepResult]:
    """Один запрос к модели: текст отдаётся по ходу, в конце — `StepResult`."""
    text_parts: list[str] = []
    calls: list[ToolCallRequest] = []
    usage: UsageReport | None = None
    stream = provider.stream_chat(
        messages,
        tools=specs,
        tool_choice="none" if final else "auto",
    )
    async with aclosing(stream):
        while (chunk := await next_before(stream, deadline)) is not None:
            if isinstance(chunk, TextDelta):
                text_parts.append(chunk.text)
                yield TextDeltaEvent(chunk.text)
            elif isinstance(chunk, ToolCallRequest):
                calls.append(chunk)
            elif isinstance(chunk, UsageReport):
                usage = chunk
    yield StepResult("".join(text_parts), tuple(calls), usage)
