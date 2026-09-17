from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import F, Max

from tickfeeddmr.market_data.models import CryptoAsset, CryptoDailyCandle
from tickfeeddmr.market_data.providers.binance.rest import (
    MAX_KLINES_LIMIT,
    BinanceRestClient,
)
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.daily_candles.budget import RunBudget
from tickfeeddmr.market_data.services.daily_candles.cursor import (
    MOSCOW_TZ,
    is_up_to_date,
    moscow_yesterday,
)
from tickfeeddmr.market_data.services.daily_candles.settings import (
    validate_poll_budget,
)
from tickfeeddmr.market_data.services.daily_candles.types import (
    CryptoCatchUpResult,
    CryptoDailyCandlesRunResult,
)
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.binance.types import BinanceCandleRow

logger = get_task_logger(__name__)

LOCK_KEY = "market_data:crypto:lock:daily_candles"

validate_poll_budget(
    "CRYPTO",
    settings.CRYPTO_DAILY_CANDLES_POLL_BUDGET_SECONDS,
    settings.CRYPTO_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
)

EPOCH_START = datetime.fromtimestamp(0, tz=UTC)


async def catch_up_asset(
    asset: CryptoAsset,
    *,
    until: date | None = None,
) -> CryptoCatchUpResult:
    """Догрузить `CryptoDailyCandle` по одному активу — от курсора до `until`.

    `until` по умолчанию — вчера по Москве. Диапазон запрашивается целиком
    (с постраничным дочитыванием, если свечей больше `MAX_KLINES_LIMIT`),
    неторговые дни ничего не стоят отдельным запросом — источник просто не
    возвращает по ним строку.
    """
    until_date = until or moscow_yesterday(now=datetime.now(UTC))
    last_date = (
        await CryptoDailyCandle.objects.filter(asset=asset)
        .order_by("-date")
        .values_list("date", flat=True)
        .afirst()
    )
    if is_up_to_date(last_date, until=until_date):
        return CryptoCatchUpResult(written=0, already_up_to_date=True)

    start_time = (
        _moscow_midnight(last_date + timedelta(days=1))
        if last_date is not None
        else EPOCH_START
    )
    end_time = _moscow_midnight(until_date)

    client = BinanceRestClient(base_url=settings.BINANCE_REST_BASE_URL)
    try:
        rows = await _fetch_all_pages(client, asset.trading_pair, start_time, end_time)
    finally:
        await client.aclose()

    if not rows:
        return CryptoCatchUpResult(written=0, already_up_to_date=False)

    candles = [
        CryptoDailyCandle(
            asset=asset,
            date=row.date,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in rows
    ]
    await CryptoDailyCandle.objects.abulk_create(candles, ignore_conflicts=True)
    return CryptoCatchUpResult(written=len(candles), already_up_to_date=False)


async def catch_up_all_assets(*, limit: int) -> CryptoDailyCandlesRunResult | None:
    """Ночной догон по активным активам — до `limit` штук за прогон.

    `None` — лок уже занят предыдущим прогоном (вызывающая задача просто
    логирует и выходит, ничего не считая ошибкой).
    """
    total = await CryptoAsset.objects.filter(is_active=True).acount()
    if total == 0:
        logger.info(
            "Догон дневных свечей крипты пропущен: нет ни одного активного "
            "актива, собирать нечего",
        )
        return CryptoDailyCandlesRunResult(0, 0, 0, budget_exhausted=False)

    try:
        async with redis_lock(
            redis_url=settings.REDIS_URL,
            key=LOCK_KEY,
            ttl_seconds=settings.CRYPTO_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
        ):
            return await _run(limit=limit)
    except LockBusyError:
        logger.info(
            "Догон дневных свечей крипты пропущен: предыдущий прогон ещё "
            "идёт (лок занят)",
        )
        return None


async def _run(*, limit: int) -> CryptoDailyCandlesRunResult:
    until_date = moscow_yesterday(now=datetime.now(UTC))
    assets = [
        asset
        async for asset in CryptoAsset.objects.filter(is_active=True)
        .annotate(last_candle_date=Max("daily_candles__date"))
        .order_by(F("last_candle_date").asc(nulls_first=True))[:limit]
    ]
    logger.info(
        f"Догон дневных свечей крипты: начат прогон, кандидатов "
        f"{len(assets)} (лимит {limit}), до {until_date}",
    )

    budget = RunBudget(settings.CRYPTO_DAILY_CANDLES_POLL_BUDGET_SECONDS)
    processed = 0
    written = 0
    skipped_errors = 0
    budget_exhausted = False
    for asset in assets:
        if budget.expired:
            budget_exhausted = True
            logger.info(
                f"Догон дневных свечей крипты: бюджет прогона исчерпан, "
                f"обработано {processed} из {len(assets)} — остальные "
                f"продолжатся следующей ночью",
            )
            break
        try:
            result = await catch_up_asset(asset, until=until_date)
        except ProviderConnectionError as exc:
            skipped_errors += 1
            logger.warning(
                f"Binance недоступен при догоне {asset.symbol}: {exc} — "
                f"актив пропущен, попробуем следующей ночью",
            )
            continue
        processed += 1
        written += result.written

    logger.info(
        f"Догон дневных свечей крипты: обработано {processed} активов, "
        f"записано {written} свечей, ошибок {skipped_errors}",
    )
    return CryptoDailyCandlesRunResult(
        processed=processed,
        written=written,
        skipped_errors=skipped_errors,
        budget_exhausted=budget_exhausted,
    )


async def _fetch_all_pages(
    client: BinanceRestClient,
    trading_pair: str,
    start_time: datetime,
    end_time: datetime,
) -> list[BinanceCandleRow]:
    rows: list[BinanceCandleRow] = []
    cursor = start_time
    while True:
        batch = await client.get_daily_candles(
            trading_pair,
            start_time=cursor,
            end_time=end_time,
        )
        if not batch:
            return rows
        rows.extend(batch)
        if len(batch) < MAX_KLINES_LIMIT:
            return rows
        cursor = _moscow_midnight(batch[-1].date + timedelta(days=1))
        if cursor > end_time:
            return rows


def _moscow_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=MOSCOW_TZ)
