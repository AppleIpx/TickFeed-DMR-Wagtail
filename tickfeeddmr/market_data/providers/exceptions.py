class ProviderError(Exception):
    """Базовая ошибка провайдера рыночных данных."""


class ProviderConnectionError(ProviderError):
    """Не удалось установить или сохранить соединение с провайдером."""


class ProviderResponseError(ProviderError):
    """Провайдер ответил ошибкой или данными неожидаемого формата."""
