from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import F, Max

from tickfeeddmr.market_data.models import StockAsset, StockDailyCandle
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

_MESSAGES = RunMessages(
    no_active_assets=(
        "Догон дневных свечей акций пропущен: нет ни одной активной "
        "бумаги, собирать нечего"
    ),
    lock_busy=(
        "Догон дневных свечей акций пропущен: предыдущий прогон ещё идёт (лок занят)"
    ),
    run_started=(
        "Догон дневных свечей акций: начат прогон, кандидатов {count} "
        "(лимит {limit}), до {until}"
    ),
    budget_exhausted=(
        "Догон дневных свечей акций: бюджет прогона исчерпан, "
        "обработано {processed} из {total} — остальные продолжатся "
        "следующей ночью"
    ),
    provider_unavailable=(
        "MOEX ISS недоступен при догоне {symbol}: {exc} — бумага "
        "пропущена, попробуем следующей ночью"
    ),
    unexpected_error=(
        "Не удалось догнать дневные свечи {symbol} — бумага пропущена, "
        "попробуем следующей ночью"
    ),
    run_summary=(
        "Догон дневных свечей акций: обработано {processed} бумаг, "
        "записано {written} свечей, ошибок {skipped_errors}"
    ),
)


async def catch_up_asset(
    asset: StockAsset,
    *,
    until: date | None = None,
) -> CatchUpResult:
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
        return CatchUpResult(written=0, already_up_to_date=True)

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
        return CatchUpResult(written=0, already_up_to_date=False)

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
    return CatchUpResult(written=len(candles), already_up_to_date=False)


async def catch_up_all_assets(*, limit: int) -> DailyCandlesRunResult | None:
    """Ночной догон по активным акциям — до `limit` штук за прогон.

    `None` — лок уже занят предыдущим прогоном.
    """
    config = CatchUpRunnerConfig(
        lock_key=LOCK_KEY,
        lock_ttl_seconds=settings.STOCK_DAILY_CANDLES_POLL_LOCK_TTL_SECONDS,
        budget_seconds=settings.STOCK_DAILY_CANDLES_POLL_BUDGET_SECONDS,
        run_budget_cls=RunBudget,
        count_active=StockAsset.objects.filter(is_active=True).acount,
        fetch_candidates=lambda limit: (
            StockAsset.objects.filter(is_active=True)
            .annotate(last_candle_date=Max("daily_candles__date"))
            .order_by(F("last_candle_date").asc(nulls_first=True))[:limit]
        ),
        catch_up_asset=catch_up_asset,
        messages=_MESSAGES,
    )
    return await run_catch_up_all(limit=limit, config=config)


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
