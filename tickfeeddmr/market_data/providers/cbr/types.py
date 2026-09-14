from decimal import Decimal

import msgspec


class CbrRateRow(msgspec.Struct, frozen=True):
    """Одна строка `ValCurs/Valute` — курс одной валюты на дату ответа."""

    cbr_id: str
    char_code: str
    nominal: int
    rate: Decimal
