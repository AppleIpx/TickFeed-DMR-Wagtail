from datetime import date
from decimal import Decimal

import msgspec


class CbrRateRow(msgspec.Struct, frozen=True):
    """Одна строка `ValCurs/Valute` — курс одной валюты на дату ответа."""

    cbr_id: str
    char_code: str
    nominal: int
    rate: Decimal


class CbrHistoryRateRow(msgspec.Struct, frozen=True):
    """Одна строка `ValCurs/Record` — курс одной валюты на дату из истории.

    `rate` — уже `VunitRate` (курс за 1 единицу валюты), деноминация
    рубля 1998 года на этом уровне не учтена — это делает вызывающий
    сервис (`services/daily_candles/fiat.py`), а не клиент.
    """

    effective_date: date
    rate: Decimal
