from datetime import datetime
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import AssetOut, DataFreshness

MOEX_DATA_DELAY_SECONDS = 900


class SecidPath(msgspec.Struct, frozen=True):
    """Path-параметр ручек акций — SECID бумаги."""

    secid: str


class StockCurrentOut(msgspec.Struct, frozen=True):
    """Текущий агрегированный снимок борда по акции"""

    asset: AssetOut
    last: str | None
    open: str | None
    high: str | None
    low: str | None
    change: str | None
    change_percent: str | None
    volume: int | None
    num_trades: int | None
    freshness: DataFreshness


class StockPricePointOut(msgspec.Struct, frozen=True):
    """Одна свеча истории цены акции — под свечной график"""

    timestamp: datetime
    open: str | None
    high: str | None
    low: str | None
    close: str | None
    volume: int | None


class StockTradeOut(msgspec.Struct, frozen=True):
    """Одна сделка из ленты акции — только для активов с `track_trades=True`"""

    timestamp: datetime
    price: str
    quantity: int
    side: Literal["buy", "sell"]
    trade_id: int
    period: str
