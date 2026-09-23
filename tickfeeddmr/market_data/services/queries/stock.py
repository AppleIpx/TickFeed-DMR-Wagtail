from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from tickfeeddmr.market_data.models import (
    StockAsset,
    StockDailyCandle,
    StockPriceSnapshot,
    StockTrade,
)
from tickfeeddmr.market_data.services.queries.cursor import fetch_cursor_page
from tickfeeddmr.market_data.services.queries.errors import (
    AssetNotFoundError,
    NoDataYetError,
    StreamAssetsNotFoundError,
    TradesNotTrackedError,
)
from tickfeeddmr.market_data.services.queries.period import (
    resolve_earliest_available,
    resolve_period,
)
from tickfeeddmr.market_data.services.queries.types import (
    IntradayPoint,
    StreamTargets,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from tickfeeddmr.market_data.services.queries.types import Cursor

INTRADAY_WINDOW = timedelta(hours=24)


async def list_assets() -> Sequence[StockAsset]:
    """Активные акции."""
    return [asset async for asset in StockAsset.objects.filter(is_active=True)]


async def resolve_stream_targets(secids: Sequence[str] | None) -> StreamTargets:
    """Какие бумаги стримить по SSE.

    В стриме акций лежат только сделки бумаг с `track_trades=True` (поллер
    не собирает ленту остальных), поэтому `secids=None` — все активные бумаги
    с включённой лентой. Ненайденные, неактивные и без ленты сделок попадают
    в `unknown` одной формулировкой. `StreamAssetsNotFoundError` — стримить
    нечего.
    """
    queryset = StockAsset.objects.filter(is_active=True, track_trades=True)
    if secids is not None:
        queryset = queryset.filter(symbol__in=secids)
    found = {asset.symbol: asset.symbol async for asset in queryset}

    if not found:
        if secids is None:
            msg = (
                "Нет бумаг с включённой лентой сделок для стрима. "
                "Актуальный список — GET /api/stocks/"
            )
        else:
            msg = (
                "Ни одна из запрошенных бумаг не найдена, не активна или без ленты "
                f"сделок: {', '.join(secids)}. Актуальный список — GET /api/stocks/"
            )
        raise StreamAssetsNotFoundError(msg)

    unknown = [] if secids is None else [s for s in secids if s not in found]
    return StreamTargets(symbols_by_stream_key=found, unknown=unknown)


async def get_current(secid: str) -> tuple[StockAsset, StockPriceSnapshot]:
    """Актив и его последний снимок борда.

    `AssetNotFoundError` — бумаги с таким `secid` нет либо она неактивна.
    `NoDataYetError` — бумага есть, но ни одного снимка ещё не записано.
    """
    asset = await StockAsset.objects.filter(symbol=secid, is_active=True).afirst()
    if asset is None:
        msg = f"Акция {secid!r} не найдена"
        raise AssetNotFoundError(msg)

    snapshot = await asset.price_snapshots.afirst()
    if snapshot is None:
        msg = f"По бумаге {secid!r} ещё нет данных"
        raise NoDataYetError(msg)

    return asset, snapshot


async def list_trades(
    secid: str,
    *,
    cursor: Cursor | None,
    limit: int,
) -> tuple[list[StockTrade], str | None]:
    """Лента сделок по бумаге — только для активов с `track_trades=True`.

    Не фильтрует по `StockTrade.period` (аукционные сделки) — решение
    этапа 8a: ISS не документирует полный список кодов, фильтрация по
    недокументированному значению рискует молча выкидывать легитимные
    сделки. Ручка отдаёт всё как есть, `period` уходит в схему
    (`StockTradeOut.period`) как есть — фильтрация, если понадобится,
    остаётся на фронте.
    """
    asset = await StockAsset.objects.filter(symbol=secid, is_active=True).afirst()
    if asset is None:
        msg = f"Акция {secid!r} не найдена"
        raise AssetNotFoundError(msg)
    if not asset.track_trades:
        msg = f"Лента сделок для {secid!r} не ведётся"
        raise TradesNotTrackedError(msg)

    queryset = StockTrade.objects.filter(asset=asset)
    return await fetch_cursor_page(queryset, cursor=cursor, limit=limit)


async def get_intraday(secid: str) -> Sequence[IntradayPoint]:
    """Скользящие последние 24 часа — снимки борда как есть, без агрегации.

    `volume` — `VOLTODAY`, накопительный итог с начала торгового дня
    (см. докстринг `LinearPricePointOut`), не сумма за интервал опроса,
    как у крипты: у акций и так один снимок в минуту, дополнительная
    агрегация не нужна.
    """
    asset = await StockAsset.objects.filter(symbol=secid, is_active=True).afirst()
    if asset is None:
        msg = f"Акция {secid!r} не найдена"
        raise AssetNotFoundError(msg)

    window_start = datetime.now(UTC) - INTRADAY_WINDOW
    return [
        IntradayPoint(
            timestamp=row.timestamp,
            # `last__isnull=False` в фильтре ниже гарантирует not-None на
            # рантайме; `cast` — только для type checker'а, значению верим.
            price=cast("Decimal", row.last),
            volume=Decimal(row.volume) if row.volume is not None else Decimal(0),
        )
        async for row in StockPriceSnapshot.objects.filter(
            asset=asset,
            timestamp__gte=window_start,
            last__isnull=False,
        ).order_by("timestamp")
    ]


async def get_history(
    secid: str,
    *,
    date_from: date | None,
    date_to: date | None,
) -> Sequence[StockDailyCandle]:
    """Дневные свечи за период.

    По умолчанию (без `date_from`/`date_to`) — либо последние
    `MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS`, либо, если настройка не
    задана, вся история бумаги с самой ранней сохранённой свечи (см.
    `resolve_period`).
    """
    asset = await StockAsset.objects.filter(symbol=secid, is_active=True).afirst()
    if asset is None:
        msg = f"Акция {secid!r} не найдена"
        raise AssetNotFoundError(msg)

    earliest_available = await resolve_earliest_available(
        date_from=date_from,
        queryset=StockDailyCandle.objects.filter(asset=asset),
        field_name="date",
    )
    frm, to = resolve_period(
        date_from=date_from,
        date_to=date_to,
        earliest_available=earliest_available,
    )
    return [
        candle
        async for candle in StockDailyCandle.objects.filter(
            asset=asset,
            date__gte=frm,
            date__lte=to,
        ).order_by("date")
    ]
