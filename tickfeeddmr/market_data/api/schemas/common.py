from datetime import datetime
from decimal import Decimal

import msgspec


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
    """Точка истории цены крипто-актива."""

    price: Decimal
    volume: Decimal | None
