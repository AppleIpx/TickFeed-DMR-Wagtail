from django.conf import settings

from tickfeeddmr.market_data.services.queries.errors import TooManyTickersError


def parse_tickers(raw: str | None) -> list[str] | None:
    """Разобрать query-параметр `symbols`/`secids`: тикеры через запятую.

    `None` — фильтра нет (пустая строка и одни запятые считаются отсутствием
    фильтра): стрим отдаёт все активные. Порядок сохраняется, повторы
    убираются. Больше `MARKET_DATA_SSE_MAX_TICKERS` — 422: это валидация
    длины входа, а не лимит соединений.
    """
    if not raw:
        return None
    tickers = list(
        dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()),
    )
    if not tickers:
        return None
    limit = settings.MARKET_DATA_SSE_MAX_TICKERS
    if len(tickers) > limit:
        msg = f"Слишком много тикеров в запросе: {len(tickers)}, максимум {limit}"
        raise TooManyTickersError(msg)
    return tickers
