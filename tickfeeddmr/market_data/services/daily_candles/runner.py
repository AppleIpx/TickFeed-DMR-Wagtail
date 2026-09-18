from __future__ import annotations

from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

import msgspec
from celery.utils.log import get_task_logger
from django.conf import settings

from tickfeeddmr.market_data.models import AssetBase
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.daily_candles.budget import RunBudget
from tickfeeddmr.market_data.services.daily_candles.cursor import moscow_yesterday
from tickfeeddmr.market_data.services.daily_candles.types import (
    CatchUpResult,
    DailyCandlesRunResult,
    RunMessages,
)
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock

if TYPE_CHECKING:
    from datetime import date

logger = get_task_logger(__name__)


class CatchUpAssetFn[AssetT: AssetBase](Protocol):
    """Тип доменного `catch_up_asset` — единственное, что раннер не даёт сам."""

    async def __call__(
        self,
        asset: AssetT,
        *,
        until: date | None = None,
    ) -> CatchUpResult: ...


class CatchUpRunnerConfig[AssetT: AssetBase](msgspec.Struct, frozen=True):
    lock_key: str
    lock_ttl_seconds: int
    budget_seconds: int
    run_budget_cls: type[RunBudget]
    count_active: Callable[[], Awaitable[int]]
    fetch_candidates: Callable[[int], AsyncIterable[AssetT]]
    catch_up_asset: CatchUpAssetFn[AssetT]
    messages: RunMessages


async def run_catch_up_all[AssetT: AssetBase](
    *,
    limit: int,
    config: CatchUpRunnerConfig[AssetT],
) -> DailyCandlesRunResult | None:
    """Ночной догон по активным активам домена — до `limit` штук за прогон.

    `None` — лок уже занят предыдущим прогоном (вызывающая задача просто
    логирует и выходит, ничего не считая ошибкой).
    """
    total = await config.count_active()
    if total == 0:
        logger.info(config.messages.no_active_assets)
        return DailyCandlesRunResult(0, 0, 0, budget_exhausted=False)

    try:
        async with redis_lock(
            redis_url=settings.REDIS_URL,
            key=config.lock_key,
            ttl_seconds=config.lock_ttl_seconds,
        ):
            return await _run(limit=limit, config=config)
    except LockBusyError:
        logger.info(config.messages.lock_busy)
        return None


async def _run[AssetT: AssetBase](
    *,
    limit: int,
    config: CatchUpRunnerConfig[AssetT],
) -> DailyCandlesRunResult:
    messages = config.messages
    until_date = moscow_yesterday(now=datetime.now(UTC))
    assets = [asset async for asset in config.fetch_candidates(limit)]
    logger.info(
        messages.run_started.format(count=len(assets), limit=limit, until=until_date),
    )

    budget = config.run_budget_cls(config.budget_seconds)
    processed = 0
    written = 0
    skipped_errors = 0
    budget_exhausted = False
    for asset in assets:
        if budget.expired:
            budget_exhausted = True
            logger.info(
                messages.budget_exhausted.format(
                    processed=processed,
                    total=len(assets),
                ),
            )
            break
        try:
            result = await config.catch_up_asset(asset, until=until_date)
        except ProviderConnectionError as exc:
            skipped_errors += 1
            logger.warning(
                messages.provider_unavailable.format(symbol=asset.symbol, exc=exc),
            )
            continue
        except Exception:
            skipped_errors += 1
            logger.exception(
                messages.unexpected_error.format(symbol=asset.symbol),
            )
            continue
        processed += 1
        written += result.written

    logger.info(
        messages.run_summary.format(
            processed=processed,
            written=written,
            skipped_errors=skipped_errors,
        ),
    )
    return DailyCandlesRunResult(
        processed=processed,
        written=written,
        skipped_errors=skipped_errors,
        budget_exhausted=budget_exhausted,
    )
