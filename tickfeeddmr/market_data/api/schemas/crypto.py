from datetime import datetime
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import (
    AssetOut,
    DataFreshness,
    HeartbeatOut,
    StreamWarningOut,
)

BINANCE_DATA_DELAY_SECONDS = 0


class SymbolPath(msgspec.Struct, frozen=True):
    """Path-параметр крипто-ручек — символ пары."""

    symbol: str


class CryptoCurrentOut(msgspec.Struct, frozen=True):
    """Текущая цена крипто-актива."""

    asset: AssetOut
    price: str
    volume: str | None
    freshness: DataFreshness


class CryptoTradeOut(msgspec.Struct, frozen=True):
    """Одна сделка из ленты крипто-актива"""

    timestamp: datetime
    price: str
    volume: str
    side: Literal["buy", "sell"]
    trade_id: str


class SymbolsQuery(msgspec.Struct, frozen=True):
    """Query SSE-стрима крипты: `symbols=BTC,ETH` — тикеры через запятую.

    Без параметра поток отдаёт все активные пары.
    """

    symbols: str | None = None


class CryptoTradeEventOut(
    msgspec.Struct,
    frozen=True,
    tag_field="kind",
    tag="trade",
):
    """Событие `trade` SSE-потока крипты: одна сделка, время — с биржи."""

    symbol: str
    timestamp: datetime
    price: str
    volume: str
    side: Literal["buy", "sell"]
    trade_id: str
    data_delay_seconds: int


CryptoStreamEventOut = CryptoTradeEventOut | StreamWarningOut | HeartbeatOut
