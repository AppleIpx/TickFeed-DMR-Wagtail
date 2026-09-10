"""Дочитывание ленты сделок MOEX по бумагам с `track_trades=True`.

Отдельная ответственность от `services/moex_ingest.py`: тот отвечает
только за запись уже полученных строк в БД (`MoexTradeIngestService`),
этот модуль — за всё, что происходит вокруг записи: проверка пустого
справочника, Redis-лок от наложения прогонов, поход в `MoexProvider`,
курсорное дочитывание ленты по страницам, бюджет времени на прогон,
логирование.

Бюджет — общий абсолютный дедлайн на все сетевые вызовы прогона
(`poll_budget_scope` вокруг каждого `get_trades_page`), а не
`asyncio.timeout` вокруг всего опроса: запись страниц и сохранение
курсора идут через async ORM в потоке, и отмена `await` поток не
прерывает — запись дошла бы до конца уже после снятия лока. Порядок
вложенности — как в `board.py`: `redis_lock` снаружи, дедлайн только
вокруг сетевого вызова, `provider.aclose()` — в `finally` вне него.

Сетевой сбой ISS (`ProviderConnectionError` после повторов клиента) или
исчерпание бюджета (`PollBudgetExceededError`) прерывает прогон целиком —
при сбое источник лежит и перебирать остальные бумаги бессмысленно, при
бюджете время прогона вышло: одна строка WARNING и проброс исключения,
оба в `throws` задачи — тик FAILURE без трейса (см.
`moex_polling/errors.py`). Уже записанные страницы прерванной бумаги
остаются в БД, но её курсор не сдвигается — следующий прогон перечитает
их, запись идемпотентна; курсоры уже пройденных бумаг сохранены.
"""

import asyncio
from typing import TYPE_CHECKING

from celery.utils.log import get_task_logger
from django.conf import settings

from tickfeeddmr.market_data.models import StockAsset
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.providers.moex import MoexProvider
from tickfeeddmr.market_data.providers.moex.client import TRADES_PAGE_ROWS
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock
from tickfeeddmr.market_data.services.moex_ingest import MoexTradeIngestService
from tickfeeddmr.market_data.services.moex_polling.errors import (
    PollBudgetExceededError,
    describe_connection_failure,
    last_failure_note,
    poll_budget_scope,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_task_logger(__name__)

TRADES_LOCK_KEY = "market_data:moex:lock:poll_trades"


class MoexTradePoller:
    """Один прогон дочитывания ленты сделок MOEX по бумагам `track_trades=True`."""

    def __init__(self) -> None:
        self._service = MoexTradeIngestService()

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
            await self._provider.aclose()

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
            new_cursor = rows[-1].trade_id
            if len(rows) < TRADES_PAGE_ROWS:
                break
        else:
            hit_page_limit = True

        if new_cursor != cursor:
            asset.last_trade_no = new_cursor
            await asset.asave(update_fields=["last_trade_no"])

        logger.info(
            f"Лента {secid}: получено {total_rows} сделок за {pages} страниц, "
            f"новый курсор {new_cursor}",
        )
        if hit_page_limit:
            logger.warning(
                f"Лента {secid}: упёрлись в лимит страниц ({page_limit}), "
                f"догон продолжится на следующем слоте",
            )


async def poll_trades() -> None:
    """Дочитывание ленты сделок MOEX для бумаг с `track_trades=True`."""
    await MoexTradePoller().run()
