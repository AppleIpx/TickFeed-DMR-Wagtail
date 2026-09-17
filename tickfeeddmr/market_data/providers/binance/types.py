from datetime import date
from decimal import Decimal

import msgspec


class BinanceCandleRow(msgspec.Struct, frozen=True):
    """Одна дневная свеча `klines` (`interval=1d`, `timeZone=3` — день по МСК)."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
