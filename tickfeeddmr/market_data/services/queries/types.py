from datetime import datetime
from decimal import Decimal

import msgspec


class Cursor(msgspec.Struct, frozen=True):
    """Разобранное значение курсора: точка `(timestamp, pk)` в потоке."""

    timestamp: datetime
    pk: int


class IntradayPoint(msgspec.Struct, frozen=True):
    """Одна точка `intraday` — общая для крипты и акций (этап 8b).

    Не модель — крипто-точка собирается агрегацией по минуте из нескольких
    строк `CryptoPriceSnapshot`, ей не соответствует одна строка БД.
    """

    timestamp: datetime
    price: Decimal
    volume: Decimal
