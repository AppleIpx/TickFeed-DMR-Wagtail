"""Строки ответов ISS MOEX, нормализованные `MoexIssClient`.

Отдельный файл от `client.py`: это чистые данные (frozen `msgspec.Struct`),
без сетевого/парсинг-кода — `client.py` создаёт их в
`_board_row_from_columns`/`_trade_row_from_columns`/
`_candle_row_from_columns`, а `provider.py`/`services/moex_ingest.py`
используют как типы для аннотаций и полей.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

import msgspec

# Официальный перечень `TTradingStatus` (документация MOEX ASTS
# `Equities59_Info`, интерфейс `Info` v.59): "T" — торговая сессия,
# "L" — аукцион закрытия, "E" — торги по цене аукциона закрытия. Все три
# статуса нужны для записи снимка борда (этап 8b, правка этапа 4):
# ограничение только статусом "T" теряло аукцион закрытия и официальную
# цену закрытия дня (18:40–18:50 МСК). Остальные значения перечня
# (N/O/C/F/B/D/I/S и фазы аукционов) трактуются как "торги не идут".
TRADING_ACTIVE_STATUSES = frozenset({"T", "L", "E"})

MOEX_DATA_DELAY_SECONDS = 900


class MoexBoardRow(msgspec.Struct, frozen=True):
    """Одна строка снимка борда ISS (`iss.only=marketdata`)."""

    secid: str
    last: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    volume: int | None
    value: Decimal | None
    num_trades: int | None
    timestamp: datetime
    trading_status: str

    @property
    def is_trading(self) -> bool:
        return self.trading_status in TRADING_ACTIVE_STATUSES


class MoexTradeRow(msgspec.Struct, frozen=True):
    """Одна строка ленты сделок ISS"""

    trade_id: int
    price: Decimal
    quantity: int
    side: Literal["buy", "sell"]
    timestamp: datetime
    period: str


class MoexCandleRow(msgspec.Struct, frozen=True):
    """Одна свеча ISS."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    value: Decimal
    volume: int
    begin: datetime
    end: datetime
