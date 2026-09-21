from datetime import datetime
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import (
    AssetOut,
    DataFreshness,
    HeartbeatOut,
    StreamWarningOut,
)


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


class SecidsQuery(msgspec.Struct, frozen=True):
    """Query SSE-стрима акций: `secids=SBER,GAZP` — тикеры через запятую.

    Без параметра поток отдаёт все активные бумаги с включённой лентой сделок.
    """

    secids: str | None = None


class StockTradeEventOut(
    msgspec.Struct,
    frozen=True,
    tag_field="kind",
    tag="trade",
):
    """Событие `trade` SSE-потока акций: одна сделка, время — от ISS.

    `data_delay_seconds` — честная метка лага бесплатной выдачи ISS (~15
    минут): `timestamp` — время сделки на бирже, а не момент получения.
    """

    secid: str
    timestamp: datetime
    price: str
    quantity: int
    side: Literal["buy", "sell"]
    trade_id: int
    period: str
    data_delay_seconds: int


StockStreamEventOut = StockTradeEventOut | StreamWarningOut | HeartbeatOut
