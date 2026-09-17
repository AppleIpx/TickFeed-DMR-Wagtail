from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import F, Max

from tickfeeddmr.market_data.models import StockAsset, StockDailyCandle
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.providers.moex.client import (
    CANDLES_PAGE_ROWS,
    MoexIssClient,
)
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
    StockCatchUpResult,
    StockDailyCandlesRunResult,
)
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.moex.types import MoexCandleRow

logger = get_task_logger(__name__)

LOCK_KEY = "market_data:stock:lock:daily_candles"

validate_poll_budget(
    "STOCK",
    settings.STOCK_DAILY_CANDLES_POLL_BUDGET_SECONDS,
    settings.STOCK_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
)

# Числовой код дневного интервала ISS `candles.json` (не путать с "1" —
# минутным интервалом по умолчанию у `MoexProvider`, тот для дневных
# свечей не используется).
DAILY_CANDLE_INTERVAL = "24"


async def catch_up_asset(
    asset: StockAsset,
    *,
    until: date | None = None,
) -> StockCatchUpResult:
    """Догрузить `StockDailyCandle` по одной бумаге — от курсора до `until`.

    `until` по умолчанию — вчера по Москве. При отсутствии свечей в БД
    начальная дата берётся через `candleborders.json`, а не угадывается
    вручную.
    """
    until_date = until or moscow_yesterday(now=datetime.now(UTC))
    last_date = (
        await StockDailyCandle.objects.filter(asset=asset)
        .order_by("-date")
        .values_list("date", flat=True)
        .afirst()
    )
    if is_up_to_date(last_date, until=until_date):
        return StockCatchUpResult(written=0, already_up_to_date=True)

    client = MoexIssClient(base_url=settings.MOEX_ISS_BASE_URL)
    try:
        if last_date is not None:
            range_start = _moscow_midnight(last_date + timedelta(days=1))
        else:
            first_available, _ = await client.get_candle_borders(
                asset.symbol,
                interval=DAILY_CANDLE_INTERVAL,
            )
            range_start = _moscow_midnight(first_available)
        range_end = _moscow_midnight(until_date)

        rows = await _fetch_all_pages(
            client,
            asset.symbol,
            start=range_start,
            end=range_end,
        )
    finally:
        await client.aclose()

    if not rows:
        return StockCatchUpResult(written=0, already_up_to_date=False)

    candles = [
        StockDailyCandle(
            asset=asset,
            # `begin`, не `end`: `end` у дневной свечи ISS — граница
            # следующего дня, брать из неё `.date()` дало бы дату на день
            # позже фактического торгового дня.
            date=row.begin.astimezone(MOSCOW_TZ).date(),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            value=row.value,
        )
        for row in rows
    ]
    await StockDailyCandle.objects.abulk_create(candles, ignore_conflicts=True)
    return StockCatchUpResult(written=len(candles), already_up_to_date=False)


async def catch_up_all_assets(*, limit: int) -> StockDailyCandlesRunResult | None:
    """Ночной догон по активным акциям — до `limit` штук за прогон.

    `None` — лок уже занят предыдущим прогоном.
    """
    total = await StockAsset.objects.filter(is_active=True).acount()
    if total == 0:
        logger.info(
            "Догон дневных свечей акций пропущен: нет ни одной активной "
            "бумаги, собирать нечего",
        )
        return StockDailyCandlesRunResult(0, 0, 0, budget_exhausted=False)

    try:
        async with redis_lock(
            redis_url=settings.REDIS_URL,
            key=LOCK_KEY,
            ttl_seconds=settings.STOCK_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
        ):
            return await _run(limit=limit)
    except LockBusyError:
        logger.info(
            "Догон дневных свечей акций пропущен: предыдущий прогон ещё "
            "идёт (лок занят)",
        )
        return None


async def _run(*, limit: int) -> StockDailyCandlesRunResult:
    until_date = moscow_yesterday(now=datetime.now(UTC))
    assets = [
        asset
        async for asset in StockAsset.objects.filter(is_active=True)
        .annotate(last_candle_date=Max("daily_candles__date"))
        .order_by(F("last_candle_date").asc(nulls_first=True))[:limit]
    ]
    logger.info(
        f"Догон дневных свечей акций: начат прогон, кандидатов "
        f"{len(assets)} (лимит {limit}), до {until_date}",
    )

    budget = RunBudget(settings.STOCK_DAILY_CANDLES_POLL_BUDGET_SECONDS)
    processed = 0
    written = 0
    skipped_errors = 0
    budget_exhausted = False
    for asset in assets:
        if budget.expired:
            budget_exhausted = True
            logger.info(
                f"Догон дневных свечей акций: бюджет прогона исчерпан, "
                f"обработано {processed} из {len(assets)} — остальные "
                f"продолжатся следующей ночью",
            )
            break
        try:
            result = await catch_up_asset(asset, until=until_date)
        except ProviderConnectionError as exc:
            skipped_errors += 1
            logger.warning(
                f"MOEX ISS недоступен при догоне {asset.symbol}: {exc} — "
                f"бумага пропущена, попробуем следующей ночью",
            )
            continue
        processed += 1
        written += result.written

    logger.info(
        f"Догон дневных свечей акций: обработано {processed} бумаг, "
        f"записано {written} свечей, ошибок {skipped_errors}",
    )
    return StockDailyCandlesRunResult(
        processed=processed,
        written=written,
        skipped_errors=skipped_errors,
        budget_exhausted=budget_exhausted,
    )


async def _fetch_all_pages(
    client: MoexIssClient,
    secid: str,
    *,
    start: datetime,
    end: datetime,
) -> list[MoexCandleRow]:
    rows: list[MoexCandleRow] = []
    start_index = 0
    while True:
        batch = await client.get_candles(
            secid,
            start=start,
            end=end,
            interval=DAILY_CANDLE_INTERVAL,
            start_index=start_index,
        )
        if not batch:
            return rows
        rows.extend(batch)
        if len(batch) < CANDLES_PAGE_ROWS:
            return rows
        start_index += len(batch)


def _moscow_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=MOSCOW_TZ)
