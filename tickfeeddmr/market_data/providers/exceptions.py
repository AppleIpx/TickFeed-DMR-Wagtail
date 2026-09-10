class ProviderError(Exception):
    """Базовая ошибка провайдера рыночных данных."""


class ProviderConnectionError(ProviderError):
    """Не удалось установить или сохранить соединение с провайдером.

    `reason`/`attempts`/`elapsed_seconds` — необязательные детали для лога
    вызывающего кода, если ошибка поднята после серии повторов (см.
    `MoexIssClient._get`): `reason` — тип последней ошибки и её усечённый,
    приведённый к одной строке текст, уже безопасный для записи в лог.
    Всё, что нужно человеку, читающему лог,
    должно быть и в самом сообщении: Celery логирует ожидаемые ошибки
    задач как `repr` исключения (см. `throws` в `market_data/tasks.py`),
    а `__cause__` при пиклинге исключения между процессами prefork-пула
    не сохраняется. В `args` передаётся только сообщение — иначе
    исключение не восстановится при unpickle (`cls(*args)`); атрибуты
    восстанавливаются из `__dict__`.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str | None = None,
        attempts: int | None = None,
        elapsed_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.attempts = attempts
        self.elapsed_seconds = elapsed_seconds


class ProviderResponseError(ProviderError):
    """Провайдер ответил ошибкой или данными неожидаемого формата."""
