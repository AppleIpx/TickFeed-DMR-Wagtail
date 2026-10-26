import gigachat.exceptions as sdk
import httpx
import pydantic

from tickfeeddmr.ai.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
)

SDK_ERRORS = (sdk.GigaChatException, httpx.TransportError, pydantic.ValidationError)


def map_error(exc: Exception) -> LLMError:
    """Ошибка слоя по исключению SDK; текст без тела ответа и заголовков."""
    if isinstance(exc, sdk.AuthenticationError | sdk.ForbiddenError):
        return LLMAuthError(f"GigaChat отклонил ключ доступа: HTTP {exc.status_code}")
    if isinstance(exc, sdk.RateLimitError | sdk.ServerError):
        return LLMConnectionError(f"GigaChat недоступен: HTTP {exc.status_code}")
    if isinstance(exc, httpx.TransportError):
        return LLMConnectionError(
            f"Не удалось связаться с GigaChat: {type(exc).__name__}",
        )
    if isinstance(exc, sdk.ResponseError):
        return LLMResponseError(f"GigaChat вернул HTTP {exc.status_code}")
    return LLMResponseError(
        f"Не удалось разобрать ответ GigaChat: {type(exc).__name__}",
    )
