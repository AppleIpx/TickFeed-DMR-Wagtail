from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.tools import stats
from tickfeeddmr.market_data.models import CryptoDailyCandle, StockDailyCandle

if TYPE_CHECKING:
    from datetime import date

    from django.db.models import QuerySet

    from tickfeeddmr.ai.services.tools.schemas import ResolvedAsset

_CANDLE_FIELDS = ("date", "open", "high", "low", "close", "volume")


def _candles_qs(a: ResolvedAsset) -> QuerySet:
    model = CryptoDailyCandle if a.market == "crypto" else StockDailyCandle
    return model.objects.filter(asset_id=a.asset_id)


def _to_candle(row: tuple) -> stats.Candle:
    d, o, h, low, c, v = row
    return stats.Candle(d, float(o), float(h), float(low), float(c), float(v))


async def fetch_candles(
    a: ResolvedAsset,
    date_from: date,
    date_to: date,
) -> list[stats.Candle]:
    """Дневные свечи актива за диапазон дат, по возрастанию даты."""
    rows = (
        _candles_qs(a)
        .filter(date__gte=date_from, date__lte=date_to)
        .order_by("date")
        .values_list(*_CANDLE_FIELDS)
    )
    return [_to_candle(row) async for row in rows]


async def fetch_candle_before(a: ResolvedAsset, day: date) -> stats.Candle | None:
    """Последняя свеча актива строго до даты."""
    row = (
        await _candles_qs(a)
        .filter(date__lt=day)
        .order_by("-date")
        .values_list(*_CANDLE_FIELDS)
        .afirst()
    )
    return None if row is None else _to_candle(row)


async def first_candle_date(a: ResolvedAsset) -> date | None:
    """Дата самой ранней дневной свечи актива."""
    return await _candles_qs(a).order_by("date").values_list("date", flat=True).afirst()
