from datetime import datetime
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import AssetOut, DataFreshness

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
