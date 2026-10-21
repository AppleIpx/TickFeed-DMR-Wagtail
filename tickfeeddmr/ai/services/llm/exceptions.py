class InvalidModelRefError(ValueError):
    """Строку с моделью не удалось разобрать на провайдера и модель.

    Ожидается формат `<провайдер>:<model_id>`, например
    `gigachat:GigaChat-2-Max` или `custom:google/gemma-4-31b-it:free`.
    Ошибка возникает, если нет двоеточия, пуст провайдер (`:model`) или пуст
    идентификатор модели (`custom:`).

    Бросается из `parse_model_ref` и только про *форму* строки. Существует ли
    такой провайдер и заданы ли для него ключи.
    """


class LLMError(Exception):
    """Базовая ошибка LLM-слоя."""


class LLMConnectionError(LLMError):
    """Провайдер недоступен: сеть, таймаут, 429/5xx после повтора."""


class LLMAuthError(LLMError):
    """Провайдер отклонил ключ или токен (401/403)."""


class LLMResponseError(LLMError):
    """Провайдер вернул прочую 4xx-ошибку или ответ, который не удалось разобрать."""
