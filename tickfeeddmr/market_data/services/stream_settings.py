from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def validate_positive(name: str, value: float) -> None:
    """Настройка должна быть положительным числом."""
    if value <= 0:
        msg = f"{name} must be a positive number, got {value}"
        raise ImproperlyConfigured(msg)


def validate_trade_stream_retention() -> None:
    """Потолок > зазор > интервал обрезки, все положительные.

    Потолок продюсера — предохранитель позади границы консьюмера (зазор);
    интервал обрезки меньше зазора, иначе граница отставала бы больше, чем
    на сам зазор.
    """
    ceiling = settings.MARKET_DATA_TRADE_STREAM_CEILING_SECONDS
    gap = settings.MARKET_DATA_TRADE_TRIM_GAP_SECONDS
    interval = settings.MARKET_DATA_TRADE_TRIM_INTERVAL_SECONDS
    if min(ceiling, gap, interval) <= 0:
        msg = (
            "MARKET_DATA_TRADE_STREAM_CEILING_SECONDS, "
            "MARKET_DATA_TRADE_TRIM_GAP_SECONDS and "
            "MARKET_DATA_TRADE_TRIM_INTERVAL_SECONDS must be positive, got "
            f"{ceiling}, {gap}, {interval}"
        )
        raise ImproperlyConfigured(msg)
    if ceiling <= gap:
        msg = (
            f"MARKET_DATA_TRADE_STREAM_CEILING_SECONDS ({ceiling}) must exceed "
            f"MARKET_DATA_TRADE_TRIM_GAP_SECONDS ({gap}): the ceiling is a "
            f"safety net behind the consumer's own trim boundary"
        )
        raise ImproperlyConfigured(msg)
    if interval >= gap:
        msg = (
            f"MARKET_DATA_TRADE_TRIM_INTERVAL_SECONDS ({interval}) must be "
            f"less than MARKET_DATA_TRADE_TRIM_GAP_SECONDS ({gap}): otherwise "
            f"the trim boundary lags behind by more than the gap itself"
        )
        raise ImproperlyConfigured(msg)


def validate_sse_settings() -> None:
    """Все `MARKET_DATA_SSE_*` положительные, heartbeat не короче окна.

    Зазор обрезки стрима должен превышать окно отбора: он защищает
    SSE-читателей, которые ещё внутри своего окна.
    """
    window = settings.MARKET_DATA_SSE_WINDOW_SECONDS
    heartbeat = settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS
    trim_gap = settings.MARKET_DATA_TRADE_TRIM_GAP_SECONDS
    validate_positive("MARKET_DATA_SSE_TOP_N", settings.MARKET_DATA_SSE_TOP_N)
    validate_positive("MARKET_DATA_SSE_WINDOW_SECONDS", window)
    validate_positive("MARKET_DATA_SSE_READ_COUNT", settings.MARKET_DATA_SSE_READ_COUNT)
    validate_positive("MARKET_DATA_SSE_HEARTBEAT_SECONDS", heartbeat)
    validate_positive(
        "MARKET_DATA_SSE_MAX_TICKERS",
        settings.MARKET_DATA_SSE_MAX_TICKERS,
    )
    if heartbeat < window:
        msg = (
            f"MARKET_DATA_SSE_HEARTBEAT_SECONDS ({heartbeat}) must not be less "
            f"than MARKET_DATA_SSE_WINDOW_SECONDS ({window})"
        )
        raise ImproperlyConfigured(msg)
    if trim_gap <= window:
        msg = (
            f"MARKET_DATA_TRADE_TRIM_GAP_SECONDS ({trim_gap}) must exceed "
            f"MARKET_DATA_SSE_WINDOW_SECONDS ({window}): the trim gap protects "
            f"SSE readers that are still inside their window"
        )
        raise ImproperlyConfigured(msg)
