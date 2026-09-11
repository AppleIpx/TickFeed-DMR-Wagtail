from django.core.exceptions import ImproperlyConfigured

_CBR_POLL_MIN_LOCK_MARGIN_SECONDS = 5


def validate_poll_budget(budget: int, ttl: int) -> None:
    """Бюджет прогона должен укладываться в TTL лока с запасом."""
    if budget <= 0:
        msg = (
            f"CBR_POLL_BUDGET_SECONDS должен быть положительным числом "
            f"секунд, получено {budget}"
        )
        raise ImproperlyConfigured(msg)
    if ttl - budget < _CBR_POLL_MIN_LOCK_MARGIN_SECONDS:
        msg = (
            f"CBR_POLL_LOCK_TTL_SECONDS ({ttl}) должен превышать "
            f"CBR_POLL_BUDGET_SECONDS ({budget}) минимум на "
            f"{_CBR_POLL_MIN_LOCK_MARGIN_SECONDS} с: этот запас покрывает "
            f"запись в БД, закрытие клиента и снятие лока, которые "
            f"выполняются внутри лока, но вне бюджета прогона"
        )
        raise ImproperlyConfigured(msg)
