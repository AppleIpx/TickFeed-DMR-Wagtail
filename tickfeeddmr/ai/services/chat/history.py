from typing import TYPE_CHECKING

from django.conf import settings

from tickfeeddmr.ai.services.errors import ChatHistoryError
from tickfeeddmr.ai.services.llm.schemas import ChatMessage

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.ai.services.chat.schemas import HistoryMessage


def validate_history(messages: Sequence[HistoryMessage]) -> list[ChatMessage]:
    """Проверить лимиты истории и привести её к сообщениям LLM-слоя."""
    if not messages:
        msg = "История сообщений пуста"
        raise ChatHistoryError(msg)
    if len(messages) > settings.AI_MAX_HISTORY_MESSAGES:
        msg = (
            f"Слишком много сообщений: {len(messages)}, "
            f"максимум {settings.AI_MAX_HISTORY_MESSAGES}"
        )
        raise ChatHistoryError(msg)
    for number, message in enumerate(messages, 1):
        if not message.content.strip():
            msg = f"Сообщение №{number} пустое"
            raise ChatHistoryError(msg)
        if len(message.content) > settings.AI_MAX_MESSAGE_CHARS:
            msg = (
                f"Сообщение №{number} длиннее {settings.AI_MAX_MESSAGE_CHARS} символов"
            )
            raise ChatHistoryError(msg)
    total_chars = sum(len(m.content) for m in messages)
    if total_chars > settings.AI_MAX_HISTORY_CHARS:
        msg = (
            f"История длиннее {settings.AI_MAX_HISTORY_CHARS} символов "
            f"({total_chars}); начните новый диалог"
        )
        raise ChatHistoryError(msg)
    if messages[-1].role != "user":
        msg = "Последнее сообщение должно быть от пользователя"
        raise ChatHistoryError(msg)
    return [ChatMessage(role=m.role, content=m.content.strip()) for m in messages]
