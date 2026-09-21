from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tickfeeddmr.market_data.services.stream_settings import validate_positive

_MOEX_POLL_MIN_LOCK_MARGIN_SECONDS = 5


def validate_poll_budget(kind: str, budget: int, ttl: int) -> None:
    """Бюджет прогона (`BOARD`/`TRADES`) должен укладываться в TTL лока с запасом.

    Инвариант: бюджет > 0, иначе каждый тик падал бы по бюджету; TTL лока
    больше бюджета не меньше чем на `_MOEX_POLL_MIN_LOCK_MARGIN_SECONDS`,
    иначе лок истечёт под живым прогоном и следующий тик наложится на него.
    Запас покрывает то, что внутри лока, но вне бюджета: запись в БД,
    `aclose()`, снятие лока.
    """
    budget_name = f"MOEX_{kind}_POLL_BUDGET_SECONDS"
    ttl_name = f"MOEX_{kind}_POLL_LOCK_TTL_SECONDS"
    if budget <= 0:
        msg = f"{budget_name} must be a positive number of seconds, got {budget}"
        raise ImproperlyConfigured(msg)
    if ttl - budget < _MOEX_POLL_MIN_LOCK_MARGIN_SECONDS:
        msg = (
            f"{ttl_name} ({ttl}) must exceed {budget_name} ({budget}) by at least "
            f"{_MOEX_POLL_MIN_LOCK_MARGIN_SECONDS}s: the margin covers DB writes, "
            f"client close and lock release that run inside the lock but outside "
            f"the run budget"
        )
        raise ImproperlyConfigured(msg)


def validate_trade_stream_settings() -> None:
    """Настройки стрима сделок акций — положительные числа."""
    validate_positive(
        "MOEX_TRADE_STREAM_RETENTION_SECONDS",
        settings.MOEX_TRADE_STREAM_RETENTION_SECONDS,
    )
    validate_positive(
        "MOEX_TRADE_STREAM_FRESHNESS_SECONDS",
        settings.MOEX_TRADE_STREAM_FRESHNESS_SECONDS,
    )
    validate_positive("MOEX_TRADE_STREAM_TOP_N", settings.MOEX_TRADE_STREAM_TOP_N)
