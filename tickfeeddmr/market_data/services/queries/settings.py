from django.core.exceptions import ImproperlyConfigured


def validate_history_default_period_days(days: int | None) -> None:
    if days is not None and days <= 0:
        msg = (
            "MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS must be a positive number "
            f"of days or unset, got {days}"
        )
        raise ImproperlyConfigured(msg)
