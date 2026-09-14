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

# ISS не публикует исчерпывающий список кодов TRADINGSTATUS в
# машиночитаемом виде. "T" ("торги идут") — единственное значение,
# подтверждённое на живых данных при подготовке этапа 4; остальные
# трактуются как "торги не идут". Если это окажется неверным для другого
# кода, лог `poll_board` (`services/moex_polling/board.py`) с сырым
# TRADINGSTATUS сделает это видимым.
TRADING_ACTIVE_STATUS = "T"


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
        return self.trading_status == TRADING_ACTIVE_STATUS


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
