from django.core.exceptions import ImproperlyConfigured

_DAILY_CANDLES_POLL_MIN_LOCK_MARGIN_SECONDS = 5


def validate_poll_budget(domain: str, budget: int, ttl: int) -> None:
    """Бюджет прогона домена дневных свечей должен укладываться в TTL лока с запасом."""
    budget_name = f"{domain}_DAILY_CANDLES_POLL_BUDGET_SECONDS"
    ttl_name = f"{domain}_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS"
    if budget <= 0:
        msg = f"{budget_name} must be a positive number of seconds, got {budget}"
        raise ImproperlyConfigured(msg)
    if ttl - budget < _DAILY_CANDLES_POLL_MIN_LOCK_MARGIN_SECONDS:
        msg = (
            f"{ttl_name} ({ttl}) must exceed {budget_name} ({budget}) by at least "
            f"{_DAILY_CANDLES_POLL_MIN_LOCK_MARGIN_SECONDS}s: the margin covers DB "
            f"writes, client close and lock release that run inside the lock but "
            f"outside the run budget"
        )
        raise ImproperlyConfigured(msg)
