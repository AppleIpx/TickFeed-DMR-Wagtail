from datetime import date

import msgspec


class Candle(msgspec.Struct, frozen=True):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class Indicators(msgspec.Struct, frozen=True):
    close: float
    sma50: float | None
    sma200: float | None
    close_vs_sma50_pct: float | None
    close_vs_sma200_pct: float | None
    rsi14: float | None
    high_52w: float | None
    low_52w: float | None
    position_52w_pct: float | None
