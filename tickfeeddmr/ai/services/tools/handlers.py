from datetime import date, timedelta
from typing import TYPE_CHECKING

import msgspec

from tickfeeddmr.ai.services.tools import stats
from tickfeeddmr.ai.services.tools.assets import resolve_asset
from tickfeeddmr.ai.services.tools.candles import (
    fetch_candle_before,
    fetch_candles,
    first_candle_date,
)
from tickfeeddmr.ai.services.tools.errors import ToolInputError
from tickfeeddmr.ai.services.tools.schemas import (
    AssetItem,
    BigMovesResult,
    CurrentResult,
    IndicatorsResult,
    ListAssetsResult,
    PeriodStatsResult,
    ResolvedAsset,
    ToolContext,
)
from tickfeeddmr.market_data.services.queries import crypto as crypto_queries
from tickfeeddmr.market_data.services.queries import stock as stock_queries

if TYPE_CHECKING:
    from tickfeeddmr.ai.services.tools.schemas import (
        BigMovesArgs,
        GetCurrentArgs,
        IndicatorsArgs,
        ListAssetsArgs,
        PeriodStatsArgs,
    )

LIST_ASSETS_MAX = 200
INDICATORS_LOOKBACK_DAYS = 450
BIG_MOVES_DEFAULT_DAYS = 365
BIG_MOVES_CONTEXT_DAYS = 45
_NO_HISTORY = "По активу ещё нет дневной истории"
_BIG_MOVES_HINT = "Сузь диапазон from/to, чтобы увидеть остальные дни"
STOCK_DELAY_NOTE = "данные ISS с задержкой ~15 минут"


def _check_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        msg = "Дата from позже даты to"
        raise ToolInputError(msg)


async def _history_start(a: ResolvedAsset) -> date:
    start = await first_candle_date(a)
    if start is None:
        raise ToolInputError(_NO_HISTORY)
    return start


async def handle_list_assets(
    args: ListAssetsArgs,
    ctx: ToolContext,
) -> ListAssetsResult:
    """Все активные крипто-активы и акции."""
    items = [
        AssetItem("crypto", a.symbol, a.display_name)
        for a in await crypto_queries.list_assets()
    ] + [
        AssetItem("stock", a.symbol, a.display_name)
        for a in await stock_queries.list_assets()
    ]
    items.sort(key=lambda i: (i.market, i.symbol))
    return ListAssetsResult(items[:LIST_ASSETS_MAX], len(items) > LIST_ASSETS_MAX)


async def handle_get_current(
    args: GetCurrentArgs,
    ctx: ToolContext,
) -> CurrentResult:
    """Последняя цена, момент и изменение за день."""
    a = await resolve_asset(args.market, args.symbol)
    if a.market == "crypto":
        _, snapshot = await crypto_queries.get_current(a.symbol)
        price = float(snapshot.price)
        before = await fetch_candle_before(a, ctx.today)
        change = None if before is None else stats.pct(price / before.close - 1)
        return CurrentResult(
            market=a.market,
            symbol=a.symbol,
            name=a.name,
            price=stats.price(price),
            currency=None,
            pair=a.trading_pair,
            as_of=snapshot.timestamp,
            change_day_pct=change,
            note=None,
        )
    _, snap = await stock_queries.get_current(a.symbol)
    if snap.last is None:
        msg = "По бумаге нет последней цены"
        raise ToolInputError(msg)
    return CurrentResult(
        market=a.market,
        symbol=a.symbol,
        name=a.name,
        price=stats.price(float(snap.last)),
        currency="RUB",
        pair=None,
        as_of=snap.timestamp,
        change_day_pct=(
            None if snap.change_percent is None else float(snap.change_percent)
        ),
        note=STOCK_DELAY_NOTE,
    )


async def handle_period_stats(
    args: PeriodStatsArgs,
    ctx: ToolContext,
) -> PeriodStatsResult:
    """Статистика по календарным периодам за диапазон."""
    a = await resolve_asset(args.market, args.symbol)
    _check_range(args.date_from, args.date_to)
    history_start = await _history_start(a)
    range_to = args.date_to or ctx.today
    range_from = args.date_from or history_start
    fetch_from = stats.previous_period_start(range_from, args.granularity)
    candles = await fetch_candles(a, fetch_from, range_to)
    if not any(c.date >= range_from for c in candles):
        msg = "Нет свечей в диапазоне"
        raise ToolInputError(msg, hint=f"История начинается с {history_start}")
    base_before = await fetch_candle_before(a, candles[0].date)
    rows = stats.period_rows(
        candles,
        base_before=base_before,
        granularity=args.granularity,
        annualization=stats.ANNUALIZATION[a.market],
        range_from=range_from,
        range_to=range_to,
        history_start=history_start,
        today=ctx.today,
    )
    rows, truncated = stats.truncate_latest(rows, ctx.max_rows)
    hint = (
        "Сузь диапазон from/to или возьми гранулярность крупнее "
        "(quarter/half_year/year)"
        if truncated
        else None
    )
    return PeriodStatsResult(
        market=a.market,
        symbol=a.symbol,
        granularity=args.granularity,
        rows=rows,
        truncated=truncated,
        hint=hint,
    )


async def handle_indicators(
    args: IndicatorsArgs,
    ctx: ToolContext,
) -> IndicatorsResult:
    """SMA, RSI и диапазон 52 недель по последней дневной свече."""
    a = await resolve_asset(args.market, args.symbol)
    candles = await fetch_candles(
        a,
        ctx.today - timedelta(days=INDICATORS_LOOKBACK_DAYS),
        ctx.today,
    )
    if not candles:
        raise ToolInputError(_NO_HISTORY)
    ind = stats.indicators(candles)
    return IndicatorsResult(
        market=a.market,
        symbol=a.symbol,
        as_of=candles[-1].date,
        **msgspec.structs.asdict(ind),
    )


async def handle_big_moves(
    args: BigMovesArgs,
    ctx: ToolContext,
) -> BigMovesResult:
    """Дни с аномальным движением цены или объёма в окне."""
    a = await resolve_asset(args.market, args.symbol)
    _check_range(args.date_from, args.date_to)
    window_to = args.date_to or ctx.today
    window_from = args.date_from or window_to - timedelta(days=BIG_MOVES_DEFAULT_DAYS)
    candles = await fetch_candles(
        a,
        window_from - timedelta(days=BIG_MOVES_CONTEXT_DAYS),
        window_to,
    )
    if not candles:
        raise ToolInputError(_NO_HISTORY)
    sigma, rows = stats.big_moves(candles, window_from=window_from, window_to=window_to)
    rows, truncated = stats.truncate_strongest(rows, ctx.max_rows)
    return BigMovesResult(
        market=a.market,
        symbol=a.symbol,
        date_from=window_from,
        date_to=window_to,
        sigma_pct=None if sigma is None else stats.pct(sigma),
        rows=rows,
        truncated=truncated,
        hint="Сузь диапазон from/to, чтобы увидеть остальные дни"
        if truncated
        else None,
    )
