import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import time as dt_time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from celery.utils.log import get_task_logger
from django.conf import settings

from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot
from tickfeeddmr.market_data.providers.cbr import CbrDailyRatesClient
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.cbr_polling.errors import (
    CbrPollBudgetExceededError,
)
from tickfeeddmr.market_data.services.cbr_polling.settings import validate_poll_budget
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from tickfeeddmr.market_data.providers.cbr import CbrRateRow

logger = get_task_logger(__name__)

CBR_LOCK_KEY = "market_data:cbr:lock:poll_rates"

# ЦБ публикует курс на день без времени суток — привязываем его к началу
# дня по московскому времени (тот же часовой пояс, что и `CELERY_TIMEZONE`,
# см. "Celery" в `CLAUDE.md`: любой домен-специфичный расчёт дат — явно в
# `Europe/Moscow`, а не в `TIME_ZONE` проекта).
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

validate_poll_budget(
    settings.CBR_POLL_BUDGET_SECONDS,
    settings.CBR_POLL_LOCK_TTL_SECONDS,
)


@dataclass(frozen=True, slots=True)
class CbrWriteResult:
    """Итог записи курсов — сырые счётчики для лога вызывающей задачи."""

    written: int
    skipped_unknown_asset: int


class CbrRatesPoller:
    """Один прогон опроса курсов ЦБ РФ по всем активным `FiatCurrency`."""

    async def run(self) -> None:
        """Публичная точка входа — пустой справочник/лок, затем сам опрос."""
        total = await FiatCurrency.objects.filter(is_active=True).acount()
        if total == 0:
            logger.info(
                "Опрос курсов ЦБ РФ пропущен: нет ни одной активной валюты, "
                "собирать нечего",
            )
            return

        try:
            async with redis_lock(
                redis_url=settings.REDIS_URL,
                key=CBR_LOCK_KEY,
                ttl_seconds=settings.CBR_POLL_LOCK_TTL_SECONDS,
            ):
                await self._poll(total=total)
        except LockBusyError:
            logger.info(
                "Опрос курсов ЦБ РФ пропущен: предыдущий прогон ещё идёт (лок занят)",
            )

    async def _poll(self, *, total: int) -> None:
        logger.info(f"Опрос курсов ЦБ РФ: активных валют {total}")

        budget = settings.CBR_POLL_BUDGET_SECONDS
        deadline = asyncio.get_running_loop().time() + budget
        client = CbrDailyRatesClient(base_url=settings.CBR_DAILY_RATES_BASE_URL)
        try:
            async with asyncio.timeout_at(deadline):
                effective_date, rows = await client.get_daily_rates()
        except ProviderConnectionError as exc:
            logger.warning(f"ЦБ РФ недоступен: {exc} — курсы за этот тик пропущены")
            raise
        except TimeoutError as exc:
            reason = client.last_failure_reason
            msg = f"ЦБ РФ не ответил за бюджет прогона {budget} с"
            if reason is not None:
                msg = f"{msg}; последняя неудачная попытка: {reason}"
            logger.warning(msg)
            raise CbrPollBudgetExceededError(msg, last_failure_reason=reason) from exc
        finally:
            await client.aclose()

        if not rows:
            logger.info("ЦБ РФ вернул пустой список курсов")
            return

        result = await self._write_snapshots(effective_date, rows)
        logger.info(
            f"Курсы ЦБ РФ на {effective_date}: записано {result.written}, "
            f"пропущено (нет активной валюты) {result.skipped_unknown_asset}",
        )

    @staticmethod
    async def _write_snapshots(
        effective_date: date,
        rows: Sequence[CbrRateRow],
    ) -> CbrWriteResult:
        """Резолвит `FiatCurrency` по `cbr_id` и пишет `FiatPriceSnapshot`."""
        cbr_ids = {row.cbr_id for row in rows}
        assets_by_cbr_id = {
            asset.cbr_id: asset
            async for asset in FiatCurrency.objects.filter(
                cbr_id__in=cbr_ids,
                is_active=True,
            )
        }

        timestamp = datetime.combine(
            effective_date,
            dt_time.min,
            tzinfo=MOSCOW_TZ,
        ).astimezone(UTC)

        snapshots = []
        skipped_unknown_asset = 0
        for row in rows:
            asset = assets_by_cbr_id.get(row.cbr_id)
            if asset is None:
                skipped_unknown_asset += 1
                continue
            snapshots.append(
                FiatPriceSnapshot(
                    asset=asset,
                    price=row.rate,
                    effective_date=effective_date,
                    timestamp=timestamp,
                ),
            )

        if snapshots:
            await FiatPriceSnapshot.objects.abulk_create(
                snapshots,
                ignore_conflicts=True,
            )
        return CbrWriteResult(
            written=len(snapshots),
            skipped_unknown_asset=skipped_unknown_asset,
        )


async def poll_rates() -> None:
    """Снимок курсов ЦБ РФ по всем активным `FiatCurrency`."""
    await CbrRatesPoller().run()
