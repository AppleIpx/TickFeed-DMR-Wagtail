from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import F, Max

from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot
from tickfeeddmr.market_data.providers.cbr import CbrDailyRatesClient
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
    FiatCatchUpResult,
    FiatDailyCandlesRunResult,
)
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock

logger = get_task_logger(__name__)

LOCK_KEY = "market_data:fiat:lock:daily_candles"

validate_poll_budget(
    "FIAT",
    settings.FIAT_DAILY_CANDLES_POLL_BUDGET_SECONDS,
    settings.FIAT_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
)

# У ЦБ нет аналога `candleborders.json` — самая ранняя реально
# наблюдавшаяся дата по любой валюте (USD/CNY, `XML_dynamic`) Запрос раньше реального
# начала истории конкретной
# валюты безвреден — ЦБ просто не возвращает по нему записей.
HISTORY_START_DATE = date(1992, 7, 1)

# Курс рубля пересчитан деноминацией с 01.01.1998 — до этой даты значения
# `VunitRate` завышены в 1000 раз: пример
# USD 30.12.1997 = 5960,00 -> 01.01.1998 = 5,96). Затрагивает все валюты
# одинаково — это деноминация рубля, не валюты.
DENOMINATION_DATE = date(1998, 1, 1)
DENOMINATION_DIVISOR = Decimal(1000)


async def catch_up_asset(
    asset: FiatCurrency,
    *,
    until: date | None = None,
) -> FiatCatchUpResult:
    """Догрузить `FiatPriceSnapshot` по одной валюте — от курсора до `until`."""
    until_date = until or moscow_yesterday(now=datetime.now(UTC))
    last_date = (
        await FiatPriceSnapshot.objects.filter(asset=asset)
        .order_by("-effective_date")
        .values_list("effective_date", flat=True)
        .afirst()
    )
    if is_up_to_date(last_date, until=until_date):
        return FiatCatchUpResult(written=0, already_up_to_date=True)

    date_from = (
        last_date + timedelta(days=1) if last_date is not None else HISTORY_START_DATE
    )

    client = CbrDailyRatesClient(base_url=settings.CBR_DAILY_RATES_BASE_URL)
    try:
        rows = await client.get_dynamic_rates(
            asset.cbr_id,
            date_from=date_from,
            date_to=until_date,
        )
    finally:
        await client.aclose()

    if not rows:
        return FiatCatchUpResult(written=0, already_up_to_date=False)

    snapshots = [
        FiatPriceSnapshot(
            asset=asset,
            price=_denominated_rate(row.rate, row.effective_date),
            effective_date=row.effective_date,
            timestamp=datetime.combine(
                row.effective_date,
                time.min,
                tzinfo=MOSCOW_TZ,
            ).astimezone(UTC),
        )
        for row in rows
    ]
    await FiatPriceSnapshot.objects.abulk_create(snapshots, ignore_conflicts=True)
    return FiatCatchUpResult(written=len(snapshots), already_up_to_date=False)


async def catch_up_all_assets(*, limit: int) -> FiatDailyCandlesRunResult | None:
    """Ночной догон по активным валютам — до `limit` штук за прогон.

    `None` — лок уже занят предыдущим прогоном.
    """
    total = await FiatCurrency.objects.filter(is_active=True).acount()
    if total == 0:
        logger.info(
            "Догон истории курсов ЦБ РФ пропущен: нет ни одной активной "
            "валюты, собирать нечего",
        )
        return FiatDailyCandlesRunResult(0, 0, 0, budget_exhausted=False)

    try:
        async with redis_lock(
            redis_url=settings.REDIS_URL,
            key=LOCK_KEY,
            ttl_seconds=settings.FIAT_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
        ):
            return await _run(limit=limit)
    except LockBusyError:
        logger.info(
            "Догон истории курсов ЦБ РФ пропущен: предыдущий прогон ещё "
            "идёт (лок занят)",
        )
        return None


async def _run(*, limit: int) -> FiatDailyCandlesRunResult:
    until_date = moscow_yesterday(now=datetime.now(UTC))
    assets = [
        asset
        async for asset in FiatCurrency.objects.filter(is_active=True)
        .annotate(last_snapshot_date=Max("price_snapshots__effective_date"))
        .order_by(F("last_snapshot_date").asc(nulls_first=True))[:limit]
    ]
    logger.info(
        f"Догон истории курсов ЦБ РФ: начат прогон, кандидатов "
        f"{len(assets)} (лимит {limit}), до {until_date}",
    )

    budget = RunBudget(settings.FIAT_DAILY_CANDLES_POLL_BUDGET_SECONDS)
    processed = 0
    written = 0
    skipped_errors = 0
    budget_exhausted = False
    for asset in assets:
        if budget.expired:
            budget_exhausted = True
            logger.info(
                f"Догон истории курсов ЦБ РФ: бюджет прогона исчерпан, "
                f"обработано {processed} из {len(assets)} — остальные "
                f"продолжатся следующей ночью",
            )
            break
        try:
            result = await catch_up_asset(asset, until=until_date)
        except ProviderConnectionError as exc:
            skipped_errors += 1
            logger.warning(
                f"ЦБ РФ недоступен при догоне {asset.symbol}: {exc} — "
                f"валюта пропущена, попробуем следующей ночью",
            )
            continue
        processed += 1
        written += result.written

    logger.info(
        f"Догон истории курсов ЦБ РФ: обработано {processed} валют, "
        f"записано {written} точек, ошибок {skipped_errors}",
    )
    return FiatDailyCandlesRunResult(
        processed=processed,
        written=written,
        skipped_errors=skipped_errors,
        budget_exhausted=budget_exhausted,
    )


def _denominated_rate(rate: Decimal, effective_date: date) -> Decimal:
    if effective_date < DENOMINATION_DATE:
        return rate / DENOMINATION_DIVISOR
    return rate
