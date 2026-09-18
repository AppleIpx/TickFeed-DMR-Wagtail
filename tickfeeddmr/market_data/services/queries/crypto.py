from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import Sum
from django.db.models.functions import TruncMinute

from tickfeeddmr.market_data.models import (
    CryptoAsset,
    CryptoDailyCandle,
    CryptoPriceSnapshot,
)
from tickfeeddmr.market_data.services.queries.cursor import fetch_cursor_page
from tickfeeddmr.market_data.services.queries.errors import (
    AssetNotFoundError,
    NoDataYetError,
)
from tickfeeddmr.market_data.services.queries.period import resolve_period
from tickfeeddmr.market_data.services.queries.types import IntradayPoint

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from tickfeeddmr.market_data.services.queries.types import Cursor

INTRADAY_WINDOW = timedelta(hours=24)


async def list_assets() -> Sequence[CryptoAsset]:
    """Активные крипто-пары."""
    return [asset async for asset in CryptoAsset.objects.filter(is_active=True)]


async def get_current(symbol: str) -> tuple[CryptoAsset, CryptoPriceSnapshot]:
    """Актив и его последний снапшот цены.

    `AssetNotFoundError` — актива с таким `symbol` нет либо он неактивен.
    `NoDataYetError` — актив есть, но ни одного снапшота ещё не записано
    (например, только что добавлен в админке, стрим ещё не догнал).
    """
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    snapshot = await asset.price_snapshots.afirst()
    if snapshot is None:
        msg = f"По активу {symbol!r} ещё нет данных"
        raise NoDataYetError(msg)

    return asset, snapshot


async def list_trades(
    symbol: str,
    *,
    cursor: Cursor | None,
    limit: int,
) -> tuple[list[CryptoPriceSnapshot], str | None]:
    """Лента сделок по активу — только строки с известными `trade_id`/`side`."""
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    queryset = CryptoPriceSnapshot.objects.filter(
        asset=asset,
        trade_id__isnull=False,
        side__isnull=False,
    )
    return await fetch_cursor_page(queryset, cursor=cursor, limit=limit)


async def get_intraday(symbol: str) -> Sequence[IntradayPoint]:
    """Скользящие последние 24 часа, агрегированные по минуте.

    `price` — цена последней сделки минуты, `volume` — сумма объёма за
    минуту (не «как есть», в отличие от акций — см. докстринг
    `LinearPricePointOut`: у крипты за сутки ~1,9 млн сделок против
    ~1440 минутных точек в ответе, без агрегации график нечитаем).
    """
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    window_start = datetime.now(UTC) - INTRADAY_WINDOW
    base_qs = CryptoPriceSnapshot.objects.filter(
        asset=asset,
        timestamp__gte=window_start,
    )

    # "Последняя сделка минуты" — `DISTINCT ON (minute)` с сортировкой
    # `minute, -timestamp` (Django `.distinct(*fields)` транслируется в
    # `DISTINCT ON`, требуя те же поля первыми в `order_by`).
    last_rows = [
        row
        async for row in base_qs.annotate(minute=TruncMinute("timestamp"))
        .order_by("minute", "-timestamp")
        .distinct("minute")
    ]
    last_price_by_minute: dict[datetime, Decimal] = {
        row.minute: row.price for row in last_rows
    }

    # Сумма объёма за минуту — отдельный запрос: агрегат «последнее
    # значение в группе» и `GROUP BY`-суммирование не выражаются одним
    # `.values().annotate()` без window-функций, которые здесь избыточны.
    volume_by_minute: dict[datetime, Decimal] = {
        row["minute"]: row["total_volume"] or Decimal(0)
        async for row in base_qs.annotate(minute=TruncMinute("timestamp"))
        .values("minute")
        .annotate(total_volume=Sum("volume"))
    }

    return [
        IntradayPoint(
            timestamp=minute,
            price=last_price_by_minute[minute],
            volume=volume_by_minute.get(minute, Decimal(0)),
        )
        for minute in sorted(last_price_by_minute)
    ]


async def get_history(
    symbol: str,
    *,
    date_from: date | None,
    date_to: date | None,
) -> Sequence[CryptoDailyCandle]:
    """Дневные свечи за период (по умолчанию — последний год)."""
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    frm, to = resolve_period(date_from=date_from, date_to=date_to)
    return [
        candle
        async for candle in CryptoDailyCandle.objects.filter(
            asset=asset,
            date__gte=frm,
            date__lte=to,
        ).order_by("date")
    ]
