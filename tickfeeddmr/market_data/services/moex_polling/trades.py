import asyncio
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING

from celery.utils.log import get_task_logger
from django.conf import settings
from redis.exceptions import ResponseError

from tickfeeddmr.market_data.models import StockAsset
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.providers.moex import MoexProvider
from tickfeeddmr.market_data.providers.moex.client import TRADES_PAGE_ROWS
from tickfeeddmr.market_data.providers.moex.types import MOEX_DATA_DELAY_SECONDS
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock
from tickfeeddmr.market_data.services.moex_ingest import MoexTradeIngestService
from tickfeeddmr.market_data.services.moex_polling.errors import (
    PollBudgetExceededError,
    describe_connection_failure,
    last_failure_note,
    poll_budget_scope,
)
from tickfeeddmr.market_data.services.moex_polling.settings import (
    validate_poll_budget,
    validate_trade_stream_settings,
)
from tickfeeddmr.market_data.services.moex_trade_stream import (
    MoexTradeStreamPublisher,
    trade_recency,
)
from tickfeeddmr.market_data.services.redis_retry import REDIS_TRANSIENT_ERRORS
from tickfeeddmr.market_data.services.stream_selection import latest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow
    from tickfeeddmr.market_data.services.stream_selection import SelectionRule

logger = get_task_logger(__name__)

TRADES_LOCK_KEY = "market_data:moex:lock:poll_trades"

validate_poll_budget(
    "TRADES",
    settings.MOEX_TRADES_POLL_BUDGET_SECONDS,
    settings.MOEX_TRADES_POLL_LOCK_TTL_SECONDS,
)
validate_trade_stream_settings()


class MoexTradePoller:
    """Один прогон дочитывания ленты сделок MOEX по бумагам `track_trades=True`."""

    def __init__(
        self,
        *,
        selection_rule: SelectionRule[MoexTradeRow] | None = None,
    ) -> None:
        self._service = MoexTradeIngestService()
        # Правило отбора уровня 1 (см. `stream_selection.py`): что из пачки
        # уйдёт в стрим для SSE. Подменяется без правки остального поллера.
        self._selection_rule: SelectionRule[MoexTradeRow] = selection_rule or partial(
            latest,
            n=settings.MOEX_TRADE_STREAM_TOP_N,
            key=trade_recency,
        )

    async def run(self) -> None:
        """Публичная точка входа — пустой справочник/лок, затем сам опрос."""
        assets = [
            asset
            async for asset in StockAsset.objects.filter(
                is_active=True,
                track_trades=True,
            )
        ]
        if not assets:
            logger.info(
                "Опрос ленты сделок MOEX пропущен: нет бумаг с track_trades=True, "
                "собирать нечего",
            )
            return

        try:
            async with redis_lock(
                redis_url=settings.REDIS_URL,
                key=TRADES_LOCK_KEY,
                ttl_seconds=settings.MOEX_TRADES_POLL_LOCK_TTL_SECONDS,
            ):
                await self._poll(assets)
        except LockBusyError:
            logger.info("Опрос MOEX пропущен: предыдущий прогон ещё идёт (лок занят)")

    async def _poll(self, assets: Sequence[StockAsset]) -> None:
        budget = settings.MOEX_TRADES_POLL_BUDGET_SECONDS
        deadline = asyncio.get_running_loop().time() + budget
        self._provider: MoexProvider = MoexProvider(
            base_url=settings.MOEX_ISS_BASE_URL,
            default_board=settings.MOEX_DEFAULT_BOARD,
        )
        self._publisher: MoexTradeStreamPublisher = MoexTradeStreamPublisher(
            redis_url=settings.REDIS_URL,
            stream_key=settings.MOEX_TRADE_STREAM_KEY,
            retention_seconds=settings.MOEX_TRADE_STREAM_RETENTION_SECONDS,
        )
        try:
            for done, asset in enumerate(assets):
                try:
                    await self._poll_asset(asset, deadline=deadline, budget=budget)
                except ProviderConnectionError as exc:
                    logger.warning(
                        f"MOEX ISS недоступен: {describe_connection_failure(exc)} — "
                        f"прогон ленты сделок прерван на {asset.symbol} "
                        f"(обработано бумаг {done} из {len(assets)})",
                    )
                    raise
                except PollBudgetExceededError as exc:
                    logger.warning(
                        f"Прогон ленты сделок не уложился в бюджет {budget} с"
                        f"{last_failure_note(exc)}, прерван на {asset.symbol} "
                        f"(обработано {done} из {len(assets)}) — догон "
                        f"продолжится на следующем тике",
                    )
                    raise
        finally:
            try:
                await self._provider.aclose()
            finally:
                await self._publisher.aclose()

    async def _poll_asset(
        self,
        asset: StockAsset,
        *,
        deadline: float,
        budget: int,
    ) -> None:
        secid = asset.symbol
        cursor = asset.last_trade_no
        logger.info(f"Лента {secid}: продолжаем с TRADENO={cursor}")

        page_limit = settings.MOEX_TRADES_PAGE_LIMIT
        total_rows = 0
        pages = 0
        new_cursor = cursor
        hit_page_limit = False
        cutoff = datetime.now(UTC) - timedelta(
            seconds=MOEX_DATA_DELAY_SECONDS
            + settings.MOEX_TRADE_STREAM_FRESHNESS_SECONDS,
        )
        candidates: list[MoexTradeRow] = []
        while pages < page_limit:
            # Под дедлайном прогона — только сетевой вызов, запись страницы
            # и сохранение курсора ниже идут вне него.
            async with poll_budget_scope(
                deadline=deadline,
                budget_seconds=budget,
                label=f"опрос ленты сделок {secid}",
                provider=self._provider,
            ):
                rows = await self._provider.get_trades_page(
                    secid,
                    since_trade_no=new_cursor,
                )
            pages += 1
            if not rows:
                break
            total_rows += await self._service.write_trades(asset, rows)
            candidates = self._selection_rule(
                [*candidates, *(row for row in rows if row.timestamp >= cutoff)],
            )
            new_cursor = rows[-1].trade_id
            if len(rows) < TRADES_PAGE_ROWS:
                break
        else:
            hit_page_limit = True

        if new_cursor != cursor:
            asset.last_trade_no = new_cursor
            await asset.asave(update_fields=["last_trade_no"])

        published = await self._publish(secid, candidates)

        logger.info(
            f"Лента {secid}: получено {total_rows} сделок за {pages} страниц, "
            f"новый курсор {new_cursor}, в стрим отправлено {published}",
        )
        if hit_page_limit:
            logger.warning(
                f"Лента {secid}: упёрлись в лимит страниц ({page_limit}), "
                f"догон продолжится на следующем слоте",
            )

    async def _publish(self, secid: str, candidates: list[MoexTradeRow]) -> int:
        """Отправить отобранные сделки в стрим; сбой стрима задачу не роняет.

        Курсор к этому моменту уже сохранён, а повтор прогона ничего бы не
        исправил (перечитанные сделки — уже в БД). Живая лента — надстройка
        над БД, её потеря на один тик не повод ронять опрос.
        """
        if not candidates:
            return 0
        try:
            return await self._publisher.publish(secid, candidates)
        except (*REDIS_TRANSIENT_ERRORS, ResponseError) as exc:
            logger.warning(
                f"Лента {secid}: не удалось отправить {len(candidates)} сделок в "
                f"стрим для SSE ({exc}); в БД они сохранены, курсор сдвинут",
            )
            return 0


async def poll_trades() -> None:
    """Дочитывание ленты сделок MOEX для бумаг с `track_trades=True`."""
    await MoexTradePoller().run()
