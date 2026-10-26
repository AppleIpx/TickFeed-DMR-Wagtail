from typing import Literal

import msgspec


class HistoryMessage(msgspec.Struct, frozen=True):
    """Сообщение истории от клиента; сервисный тип, не зависящий от API-схем."""

    role: Literal["user", "assistant"]
    content: str
