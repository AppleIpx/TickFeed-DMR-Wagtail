from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import F, Max

from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot
from tickfeeddmr.market_data.providers.cbr import CbrDailyRatesClient
from tickfeeddmr.market_data.services.daily_candles.budget import RunBudget
from tickfeeddmr.market_data.services.daily_candles.cursor import (
    MOSCOW_TZ,
    is_up_to_date,
    moscow_yesterday,
)
from tickfeeddmr.market_data.services.daily_candles.runner import (
    CatchUpRunnerConfig,
    run_catch_up_all,
)
from tickfeeddmr.market_data.services.daily_candles.settings import (
    validate_poll_budget,
)
from tickfeeddmr.market_data.services.daily_candles.types import (
    CatchUpResult,
    DailyCandlesRunResult,
    RunMessages,
)

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

_MESSAGES = RunMessages(
    no_active_assets=(
        "Догон истории курсов ЦБ РФ пропущен: нет ни одной активной "
        "валюты, собирать нечего"
    ),
    lock_busy=(
        "Догон истории курсов ЦБ РФ пропущен: предыдущий прогон ещё идёт (лок занят)"
    ),
    run_started=(
        "Догон истории курсов ЦБ РФ: начат прогон, кандидатов {count} "
        "(лимит {limit}), до {until}"
    ),
    budget_exhausted=(
        "Догон истории курсов ЦБ РФ: бюджет прогона исчерпан, "
        "обработано {processed} из {total} — остальные продолжатся "
        "следующей ночью"
    ),
    provider_unavailable=(
        "ЦБ РФ недоступен при догоне {symbol}: {exc} — валюта пропущена, "
        "попробуем следующей ночью"
    ),
    unexpected_error=(
        "Не удалось догнать историю курса {symbol} — валюта пропущена, "
        "попробуем следующей ночью"
    ),
    run_summary=(
        "Догон истории курсов ЦБ РФ: обработано {processed} валют, "
        "записано {written} точек, ошибок {skipped_errors}"
    ),
)


async def catch_up_asset(
    asset: FiatCurrency,
    *,
    until: date | None = None,
) -> CatchUpResult:
    """Догрузить `FiatPriceSnapshot` по одной валюте — от курсора до `until`."""
    until_date = until or moscow_yesterday(now=datetime.now(UTC))
    last_date = (
        await FiatPriceSnapshot.objects.filter(asset=asset)
        .order_by("-effective_date")
        .values_list("effective_date", flat=True)
        .afirst()
    )
    if is_up_to_date(last_date, until=until_date):
        return CatchUpResult(written=0, already_up_to_date=True)

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
        return CatchUpResult(written=0, already_up_to_date=False)

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
    return CatchUpResult(written=len(snapshots), already_up_to_date=False)


async def catch_up_all_assets(*, limit: int) -> DailyCandlesRunResult | None:
    """Ночной догон по активным валютам — до `limit` штук за прогон.

    `None` — лок уже занят предыдущим прогоном.
    """
    config = CatchUpRunnerConfig(
        lock_key=LOCK_KEY,
        lock_ttl_seconds=settings.FIAT_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
        budget_seconds=settings.FIAT_DAILY_CANDLES_POLL_BUDGET_SECONDS,
        run_budget_cls=RunBudget,
        count_active=FiatCurrency.objects.filter(is_active=True).acount,
        fetch_candidates=lambda limit: (
            FiatCurrency.objects.filter(is_active=True)
            .annotate(last_snapshot_date=Max("price_snapshots__effective_date"))
            .order_by(F("last_snapshot_date").asc(nulls_first=True))[:limit]
        ),
        catch_up_asset=catch_up_asset,
        messages=_MESSAGES,
    )
    return await run_catch_up_all(limit=limit, config=config)


def _denominated_rate(rate: Decimal, effective_date: date) -> Decimal:
    if effective_date < DENOMINATION_DATE:
        return rate / DENOMINATION_DIVISOR
    return rate
