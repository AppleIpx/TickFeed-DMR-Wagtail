from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CbrRateRow:
    """Одна строка `ValCurs/Valute` — курс одной валюты на дату ответа."""

    cbr_id: str
    char_code: str
    nominal: int
    rate: Decimal
