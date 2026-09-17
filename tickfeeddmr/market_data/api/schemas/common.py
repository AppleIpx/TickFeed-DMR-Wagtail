from datetime import datetime
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
    """Точка истории цены крипто-актива"""

    price: str
    volume: str | None


class CursorPage[ItemT](msgspec.Struct, frozen=True):
    """Курсорная страница списочного ответа"""

    items: list[ItemT]
    next_cursor: str | None
    freshness: DataFreshness


class CursorQuery(msgspec.Struct, frozen=True):
    """Query-параметры курсорной пагинации ленты сделок"""

    cursor: str | None = None
    limit: Annotated[int, msgspec.Meta(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT
