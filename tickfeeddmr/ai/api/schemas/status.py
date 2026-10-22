from datetime import datetime

import msgspec


class AiUsageOut(msgspec.Struct, frozen=True):
    """Расход ИИ за текущие московские сутки и момент сброса счётчика."""

    requests: int
    requests_limit: int
    tokens: int
    tokens_limit: int
    resets_at: datetime


class AiStatusOut(msgspec.Struct, frozen=True):
    """Состояние ИИ-аналитика: включён ли он, лимиты истории и расход за сегодня."""

    enabled: bool
    model: str | None
    max_messages: int
    max_message_chars: int
    usage: AiUsageOut | None
