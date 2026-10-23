import statistics
from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.tools.schemas import BigMoveRow
from tickfeeddmr.ai.services.tools.stats.rounding import pct_or_none

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from tickfeeddmr.ai.services.tools.schemas import MoveReason
    from tickfeeddmr.ai.services.tools.stats.schemas import Candle

BIG_MOVE_SIGMA = 3.0
VOLUME_SPIKE_RATIO = 3.0
VOLUME_LOOKBACK = 20


def big_moves(
    candles: Sequence[Candle],
    *,
    window_from: date,
    window_to: date,
) -> tuple[float | None, list[BigMoveRow]]:
    """σ доходности окна и дни с движением от 3σ или объёмом от 3× медианы."""
    in_window = [i for i, c in enumerate(candles) if window_from <= c.date <= window_to]
    returns = {
        i: candles[i].close / candles[i - 1].close - 1 for i in in_window if i >= 1
    }
    sigma = statistics.stdev(returns.values()) if len(returns) >= 2 else None  # noqa: PLR2004
    rows: list[BigMoveRow] = []
    for i in in_window:
        ret = returns.get(i)
        z = ret / sigma if ret is not None and sigma else None
        previous = candles[i - VOLUME_LOOKBACK : i] if i >= VOLUME_LOOKBACK else None
        median = statistics.median(c.volume for c in previous) if previous else None
        ratio = candles[i].volume / median if median else None
        gap = candles[i].open / candles[i - 1].close - 1 if i >= 1 else None
        reasons: list[MoveReason] = []
        if z is not None and abs(z) >= BIG_MOVE_SIGMA:
            reasons.append("price")
        if ratio is not None and ratio >= VOLUME_SPIKE_RATIO:
            reasons.append("volume")
        if reasons:
            rows.append(
                BigMoveRow(
                    date=candles[i].date,
                    change_pct=pct_or_none(ret),
                    z_score=None if z is None else round(z, 2),
                    gap_pct=pct_or_none(gap),
                    volume_ratio=None if ratio is None else round(ratio, 2),
                    reasons=reasons,
                ),
            )
    return sigma, rows
