from http import HTTPStatus

from config.api_base import DomainError


class AiDisabledError(DomainError):
    """ИИ-чат выключен настройкой `AI_ENABLED`."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE


class AiUnavailableError(DomainError):
    """Не удалось проверить дневной лимит: Redis недоступен (отказ при сбое)."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE


class AiQuotaExceededError(DomainError):
    """Дневной лимит обращений к LLM или токенов исчерпан."""

    status_code = HTTPStatus.TOO_MANY_REQUESTS


class ChatHistoryError(DomainError):
    """История сообщений нарушает лимиты или порядок ролей."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
