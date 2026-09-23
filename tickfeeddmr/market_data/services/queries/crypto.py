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
from tickfeeddmr.market_data.providers.binance import EXCHANGE
from tickfeeddmr.market_data.services.queries.cursor import fetch_cursor_page
from tickfeeddmr.market_data.services.queries.errors import (
    AssetNotFoundError,
    NoDataYetError,
    StreamAssetsNotFoundError,
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


async def list_assets() -> Sequence[CryptoAsset]:
    """Активные крипто-пары."""
    return [asset async for asset in CryptoAsset.objects.filter(is_active=True)]


async def resolve_stream_targets(symbols: Sequence[str] | None) -> StreamTargets:
    """Какие крипто-пары стримить по SSE.

    `symbols=None` — все активные пары Binance (именно Binance: в стриме
    лежат только его сделки). Иначе только перечисленные; ненайденные и
    неактивные попадают в `unknown` (отвечаем им намеренно одинаково, см.
    `AssetNotFoundError`). `StreamAssetsNotFoundError` — стримить нечего.
    """
    queryset = CryptoAsset.objects.filter(exchange=EXCHANGE, is_active=True)
    if symbols is not None:
        queryset = queryset.filter(symbol__in=symbols)
    by_pair = {asset.trading_pair: asset.symbol async for asset in queryset}

    if not by_pair:
        if symbols is None:
            msg = (
                "Нет активных крипто-активов для стрима. "
                "Актуальный список — GET /api/crypto/assets/"
            )
        else:
            msg = (
                "Ни один из запрошенных тикеров не найден или не активен: "
                f"{', '.join(symbols)}. Актуальный список — GET /api/crypto/assets/"
            )
        raise StreamAssetsNotFoundError(msg)

    found = set(by_pair.values())
    unknown = [] if symbols is None else [s for s in symbols if s not in found]
    return StreamTargets(symbols_by_stream_key=by_pair, unknown=unknown)


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
    """Дневные свечи за период.

    По умолчанию (без `date_from`/`date_to`) — либо последние
    `MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS`, либо, если настройка не
    задана, вся история актива с самой ранней сохранённой свечи (см.
    `resolve_period`).
    """
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    earliest_available = await resolve_earliest_available(
        date_from=date_from,
        queryset=CryptoDailyCandle.objects.filter(asset=asset),
        field_name="date",
    )
    frm, to = resolve_period(
        date_from=date_from,
        date_to=date_to,
        earliest_available=earliest_available,
    )
    return [
        candle
        async for candle in CryptoDailyCandle.objects.filter(
            asset=asset,
            date__gte=frm,
            date__lte=to,
        ).order_by("date")
    ]
