import calendar
import math
import statistics
from datetime import date, timedelta
from itertools import groupby, pairwise
from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.tools.schemas import PeriodRow
from tickfeeddmr.ai.services.tools.stats.rounding import pct, pct_or_none, price

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.ai.services.tools.schemas import Granularity, Market
    from tickfeeddmr.ai.services.tools.stats.schemas import Candle

ANNUALIZATION: dict[Market, int] = {"crypto": 365, "stock": 252}

PeriodKey = tuple[int, int]


def period_key(d: date, granularity: Granularity) -> PeriodKey:
    """Ключ календарного периода даты: `(год, номер части)`."""
    match granularity:
        case "year":
            return (d.year, 0)
        case "half_year":
            return (d.year, 1 if d.month <= 6 else 2)  # noqa: PLR2004
        case "quarter":
            return (d.year, (d.month - 1) // 3 + 1)
        case "month":
            return (d.year, d.month)


def period_bounds(key: PeriodKey, granularity: Granularity) -> tuple[date, date]:
    """Первый и последний календарный день периода."""
    year, part = key
    match granularity:
        case "year":
            first_month, last_month = 1, 12
        case "half_year":
            first_month, last_month = (1, 6) if part == 1 else (7, 12)
        case "quarter":
            first_month = (part - 1) * 3 + 1
            last_month = first_month + 2
        case "month":
            first_month = last_month = part
    last_day = calendar.monthrange(year, last_month)[1]
    return date(year, first_month, 1), date(year, last_month, last_day)


def period_label(key: PeriodKey, granularity: Granularity) -> str:
    """Метка периода: `2024`, `2024-H1`, `2024-Q3`, `2024-05`."""
    year, part = key
    match granularity:
        case "year":
            return f"{year}"
        case "half_year":
            return f"{year}-H{part}"
        case "quarter":
            return f"{year}-Q{part}"
        case "month":
            return f"{year}-{part:02d}"


def previous_period_start(d: date, granularity: Granularity) -> date:
    """Первый день календарного периода перед периодом даты."""
    start, _ = period_bounds(period_key(d, granularity), granularity)
    previous_end = start - timedelta(days=1)
    return period_bounds(period_key(previous_end, granularity), granularity)[0]


def _max_drawdown(base: float, closes: Sequence[float]) -> float:
    """Наибольшее падение от накопленного пика, доля от 0 до 1."""
    peak, drawdown = base, 0.0
    for close in closes:
        peak = max(peak, close)
        drawdown = max(drawdown, 1 - close / peak)
    return drawdown


def _annualized_volatility(
    base: float,
    closes: Sequence[float],
    annualization: int,
) -> float | None:
    """Годовое выборочное σ лог-доходностей; `None`, если их меньше двух."""
    log_returns = [math.log(b / a) for a, b in pairwise([base, *closes])]
    if len(log_returns) < 2:  # noqa: PLR2004
        return None
    return statistics.stdev(log_returns) * math.sqrt(annualization)


def period_rows(  # noqa: PLR0913
    candles: Sequence[Candle],
    *,
    base_before: Candle | None,
    granularity: Granularity,
    annualization: int,
    range_from: date,
    range_to: date,
    history_start: date,
    today: date,
) -> list[PeriodRow]:
    """Доходность, просадку, волатильность и изменение объёма по периодам."""
    first_key = period_key(range_from, granularity)
    effective_from = max(range_from, history_start)
    effective_to = min(range_to, today)
    prev_close = base_before.close if base_before else None
    prev_avg_volume: float | None = None
    rows: list[PeriodRow] = []
    for key, group in groupby(candles, key=lambda c: period_key(c.date, granularity)):
        cs = list(group)
        closes = [c.close for c in cs]
        base = prev_close if prev_close is not None else cs[0].open
        avg_volume = statistics.fmean(c.volume for c in cs)
        if key >= first_key:
            start, end = period_bounds(key, granularity)
            volume_change = (
                avg_volume / prev_avg_volume - 1 if prev_avg_volume else None
            )
            volatility = _annualized_volatility(base, closes, annualization)
            rows.append(
                PeriodRow(
                    label=period_label(key, granularity),
                    first_date=cs[0].date,
                    last_date=cs[-1].date,
                    trading_days=len(cs),
                    close=price(closes[-1]),
                    return_pct=pct(closes[-1] / base - 1),
                    max_drawdown_pct=-pct(_max_drawdown(base, closes)),
                    volatility_pct=pct_or_none(volatility),
                    volume_change_pct=pct_or_none(volume_change),
                    partial=start < effective_from or end > effective_to,
                ),
            )
        prev_close, prev_avg_volume = closes[-1], avg_volume
    return rows
