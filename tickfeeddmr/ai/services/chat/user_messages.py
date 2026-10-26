from tickfeeddmr.ai.services.errors import AiQuotaExceededError, AiUnavailableError
from tickfeeddmr.ai.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
)

INTERNAL_ERROR_MESSAGE = "Внутренняя ошибка ИИ-аналитика"


def user_message(exc: Exception) -> str:
    """Текст ошибки для пользователя без деталей провайдера."""
    if isinstance(exc, AiQuotaExceededError | AiUnavailableError):
        return str(exc)
    if isinstance(exc, TimeoutError):
        return "Ответ занял слишком много времени"
    if isinstance(exc, LLMAuthError):
        return "ИИ-провайдер отклонил ключ доступа — сообщите администратору"
    if isinstance(exc, LLMConnectionError):
        return "ИИ-провайдер недоступен, попробуйте позже"
    if isinstance(exc, LLMError):
        return "ИИ-провайдер вернул ошибку"
    return INTERNAL_ERROR_MESSAGE
