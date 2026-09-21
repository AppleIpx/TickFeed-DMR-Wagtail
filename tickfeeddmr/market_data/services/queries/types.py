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


class StreamTargets(msgspec.Struct, frozen=True):
    """Результат резолва тикеров для SSE-стрима: кого стримим, что не нашлось.

    `symbols_by_stream_key` — ключ, под которым тикер лежит в Redis Stream
    (у крипты `trading_pair`, у акций `secid`), -> символ, под которым он
    известен API. Отдельный тип, а не голый dict, чтобы контроллер и
    презентер не знали, кому какой ключ принадлежит.
    """

    symbols_by_stream_key: dict[str, str]
    unknown: list[str]
