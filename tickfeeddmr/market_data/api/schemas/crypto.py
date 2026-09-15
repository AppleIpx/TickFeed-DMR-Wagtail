from datetime import datetime
from decimal import Decimal
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import AssetOut, DataFreshness

BINANCE_DATA_DELAY_SECONDS = 0


class CryptoCurrentOut(msgspec.Struct, frozen=True):
    """Текущая цена крипто-актива."""

    asset: AssetOut
    price: Decimal
    volume: Decimal | None
    freshness: DataFreshness


class CryptoTradeOut(msgspec.Struct, frozen=True):
    """Одна сделка из ленты крипто-актива"""

    timestamp: datetime
    price: Decimal
    volume: Decimal
    side: Literal["buy", "sell"]
    trade_id: str
