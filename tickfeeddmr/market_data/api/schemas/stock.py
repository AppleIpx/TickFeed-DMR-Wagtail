from datetime import datetime
from decimal import Decimal
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import AssetOut, DataFreshness

MOEX_DATA_DELAY_SECONDS = 900


class StockCurrentOut(msgspec.Struct, frozen=True):
    """Текущий агрегированный снимок борда по акции"""

    asset: AssetOut
    last: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    volume: int | None
    num_trades: int | None
    freshness: DataFreshness


class StockPricePointOut(msgspec.Struct, frozen=True):
    """Одна свеча истории цены акции — под свечной график"""

    timestamp: datetime
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None


class StockTradeOut(msgspec.Struct, frozen=True):
    """Одна сделка из ленты акции — только для активов с `track_trades=True`."""

    timestamp: datetime
    price: Decimal
    quantity: int
    side: Literal["buy", "sell"]
    trade_id: int
