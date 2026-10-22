from typing import Literal

import msgspec


class ChatMessageIn(msgspec.Struct, frozen=True):
    """Сообщение истории диалога: только реплики пользователя и ассистента."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequestIn(msgspec.Struct, frozen=True):
    """Тело запроса чата: вся история диалога, последним — вопрос пользователя."""

    messages: list[ChatMessageIn]


class ChatTextDeltaOut(
    msgspec.Struct,
    frozen=True,
    tag_field="kind",
    tag="text_delta",
):
    """Очередной фрагмент текста ответа."""

    text: str


class ChatToolCallOut(
    msgspec.Struct,
    frozen=True,
    tag_field="kind",
    tag="tool_call",
):
    """Модель обращается к данным системы; `label` — подпись для интерфейса."""

    name: str
    label: str


class ChatDoneOut(
    msgspec.Struct,
    frozen=True,
    tag_field="kind",
    tag="done",
):
    """Ответ завершён."""

    model: str


class ChatErrorOut(
    msgspec.Struct,
    frozen=True,
    tag_field="kind",
    tag="error",
):
    """Ответ прерван; `message` можно показать пользователю."""

    message: str


ChatEventOut = ChatTextDeltaOut | ChatToolCallOut | ChatDoneOut | ChatErrorOut
