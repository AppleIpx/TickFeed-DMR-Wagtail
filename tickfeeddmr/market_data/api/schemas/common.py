from datetime import date, datetime
from typing import Annotated

import msgspec

from tickfeeddmr.market_data.services.queries.cursor import DEFAULT_LIMIT, MAX_LIMIT


class AssetOut(msgspec.Struct, frozen=True):
    """Общий вид торгуемого актива в ответах API — крипта, фиат или акция."""

    symbol: str
    display_name: str
    is_active: bool


class DataFreshness(msgspec.Struct, frozen=True):
    """Честная метка свежести данных: показывает лаг источника как есть."""

    timestamp: datetime
    data_delay_seconds: int
    is_realtime: bool


class PricePointBase(msgspec.Struct, frozen=True):
    """Общая часть точки истории цены — момент, к которому она относится."""

    timestamp: datetime


class PricePointOut(PricePointBase, frozen=True):
    """Дневная точка истории цены крипто-актива (CryptoDailyCandle).

    `close`, не `price`: симметрично `StockPricePointOut`, у которой
    OHLC — не экстремумы сессии (как у `intraday`), а настоящая дневная
    свеча, то же самое, что и здесь.
    """

    open: str
    high: str
    low: str
    close: str
    volume: str


class LinearPricePointOut(msgspec.Struct, frozen=True):
    """Точка `intraday` — общая линейная схема для крипты и акций."""

    timestamp: datetime
    price: str
    volume: str


class IntradayOut(msgspec.Struct, frozen=True):
    """Ответ `intraday` — точки за скользящие 24 часа + одна свежесть на весь ответ."""

    points: list[LinearPricePointOut]
    freshness: DataFreshness


class HistoryQuery(
    msgspec.Struct,
    frozen=True,
    rename={"date_from": "from", "date_to": "to"},
):
    """Query-параметры `history` — период опционален, по умолчанию последний год."""

    date_from: date | None = None
    date_to: date | None = None


class CursorPage[ItemT](msgspec.Struct, frozen=True):
    """Курсорная страница списочного ответа"""

    items: list[ItemT]
    next_cursor: str | None
    freshness: DataFreshness


class CursorQuery(msgspec.Struct, frozen=True):
    """Query-параметры курсорной пагинации ленты сделок"""

    cursor: str | None = None
    limit: Annotated[int, msgspec.Meta(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT
