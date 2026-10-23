import statistics
from datetime import timedelta
from itertools import pairwise
from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.tools.stats.rounding import pct, price
from tickfeeddmr.ai.services.tools.stats.schemas import Indicators

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.ai.services.tools.stats.schemas import Candle

SMA_SHORT = 50
SMA_LONG = 200
RSI_PERIOD = 14
RANGE_52W_DAYS = 365


def sma(closes: Sequence[float], n: int) -> float | None:
    """Простая скользящая средняя последних `n` значений; `None`, если истории мало."""
    return statistics.fmean(closes[-n:]) if len(closes) >= n else None


def rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> float | None:
    """RSI по сглаживанию Уайлдера; `None`, если истории мало."""
    changes = [b - a for a, b in pairwise(closes)]
    if len(changes) < period:
        return None
    gain = statistics.fmean(max(x, 0) for x in changes[:period])
    loss = statistics.fmean(max(-x, 0) for x in changes[:period])
    for x in changes[period:]:
        gain = (gain * (period - 1) + max(x, 0)) / period
        loss = (loss * (period - 1) + max(-x, 0)) / period
    if loss == 0:
        return 50.0 if gain == 0 else 100.0
    return 100 - 100 / (1 + gain / loss)


def range_52w(candles: Sequence[Candle]) -> tuple[float, float, float | None] | None:
    """Максимум, минимум за 365 дней и положение закрытия в диапазоне, %."""
    if not candles:
        return None
    last = candles[-1]
    cutoff = last.date - timedelta(days=RANGE_52W_DAYS)
    window = [c for c in candles if c.date > cutoff]
    high = max(c.high for c in window)
    low = min(c.low for c in window)
    position = None if high == low else (last.close - low) / (high - low) * 100
    return high, low, position


def indicators(candles: Sequence[Candle]) -> Indicators:
    """SMA50/200, отклонения от них, RSI14 и диапазон 52 недель по последней свече."""
    closes = [c.close for c in candles]
    close = closes[-1]
    sma50, sma200 = sma(closes, SMA_SHORT), sma(closes, SMA_LONG)
    year_range = range_52w(candles)
    high, low, position = year_range if year_range else (None, None, None)
    rsi14 = rsi(closes)
    return Indicators(
        close=price(close),
        sma50=None if sma50 is None else price(sma50),
        sma200=None if sma200 is None else price(sma200),
        close_vs_sma50_pct=None if sma50 is None else pct(close / sma50 - 1),
        close_vs_sma200_pct=None if sma200 is None else pct(close / sma200 - 1),
        rsi14=None if rsi14 is None else round(rsi14, 2),
        high_52w=None if high is None else price(high),
        low_52w=None if low is None else price(low),
        position_52w_pct=None if position is None else round(position, 2),
    )
