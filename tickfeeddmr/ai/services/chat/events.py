from typing import Literal

import msgspec


class TextDeltaEvent(msgspec.Struct, frozen=True):
    """Очередной фрагмент текста ответа."""

    text: str


class ToolCallEvent(msgspec.Struct, frozen=True):
    """Модель вызывает инструмент; `arguments_json` нужен только стенду."""

    name: str
    label: str
    arguments_json: str


class DoneEvent(msgspec.Struct, frozen=True):
    """Ответ закончен успешно."""

    model: str


class ErrorEvent(msgspec.Struct, frozen=True):
    """Ответ прерван; `message` безопасен для показа пользователю."""

    message: str


class ToolCallRecord(msgspec.Struct, frozen=True):
    """Вызов инструмента в сводке прогона."""

    name: str
    arguments_json: str


class RunSummaryEvent(msgspec.Struct, frozen=True):
    """Итог прогона для стенда и лога; клиенту по SSE не отправляется."""

    model: str
    steps: int
    tool_calls: list[ToolCallRecord]
    prompt_tokens: int
    completion_tokens: int
    tokens_estimated: bool
    duration_seconds: float
    outcome: Literal["done", "error"]
    error: str | None


ChatEvent = TextDeltaEvent | ToolCallEvent | DoneEvent | ErrorEvent | RunSummaryEvent
