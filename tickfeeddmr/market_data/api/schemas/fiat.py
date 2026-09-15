from datetime import date
from decimal import Decimal
from typing import Literal

import msgspec

from tickfeeddmr.market_data.api.schemas.common import (
    AssetOut,
    DataFreshness,
    PricePointBase,
)

CBR_DATA_DELAY_SECONDS = 86_400
CBR_SOURCE_LABEL = "ЦБ РФ"


class FiatRateOut(msgspec.Struct, frozen=True):
    """Курс валюты ЦБ РФ"""

    asset: AssetOut
    iso_code: str
    rate: Decimal
    effective_date: date
    source: Literal["ЦБ РФ"]
    freshness: DataFreshness


class FiatRatePointOut(PricePointBase, frozen=True):
    """Точка истории курса валюты."""

    effective_date: date
    rate: Decimal
