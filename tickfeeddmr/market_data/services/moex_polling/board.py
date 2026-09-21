"""Опрос снимка борда MOEX по всем активным `StockAsset` борда.

Отдельная ответственность от `services/moex_ingest.py`: тот отвечает
только за запись уже полученных строк в БД (`MoexBoardSnapshotService`),
этот модуль — за всё, что происходит вокруг записи: проверка пустого
справочника, Redis-лок от наложения прогонов, поход в `MoexProvider`,
бюджет времени на прогон, логирование лага данных ISS.

Недоступность ISS (`ProviderConnectionError` после повторов клиента) и
превышение бюджета прогона (`PollBudgetExceededError`): одна строка
WARNING и проброс дальше, оба в `throws` задачи — тик FAILURE без трейса
(см. `moex_polling/errors.py`).

Порядок вложенности важен: `redis_lock` снаружи, бюджет
(`poll_budget_scope`, `asyncio.timeout_at` внутри) — только вокруг
сетевого вызова. Так отмена по бюджету превращается в
`PollBudgetExceededError` на выходе из своего scope, до
того как управление дойдёт до `provider.aclose()` и до снятия лока в
`finally` у `redis_lock` — ни то, ни другое не выполняется внутри
отменённого scope. Запись в БД под бюджет не попадает: async ORM
выполняет запрос в потоке, отмена `await` поток не прерывает — запись
дошла бы до конца уже после снятия лока.
"""

import asyncio
import logging
from datetime import UTC, datetime

from celery.utils.log import get_task_logger
from django.conf import settings

from tickfeeddmr.market_data.models import StockAsset
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.providers.moex import MoexProvider
from tickfeeddmr.market_data.providers.moex.timeutils import MOSCOW_TZ
from tickfeeddmr.market_data.services.locks import LockBusyError, redis_lock
from tickfeeddmr.market_data.services.moex_ingest import MoexBoardSnapshotService
from tickfeeddmr.market_data.services.moex_polling.errors import (
    PollBudgetExceededError,
    describe_connection_failure,
    last_failure_note,
    poll_budget_scope,
)
from tickfeeddmr.market_data.services.moex_polling.settings import validate_poll_budget

logger = get_task_logger(__name__)

BOARD_LOCK_KEY = "market_data:moex:lock:poll_board"

validate_poll_budget(
    "BOARD",
    settings.MOEX_BOARD_POLL_BUDGET_SECONDS,
    settings.MOEX_BOARD_POLL_LOCK_TTL_SECONDS,
)


class MoexBoardPoller:
    """Один прогон снимка борда MOEX по всем активным `StockAsset` борда."""

    def __init__(self, *, board: str) -> None:
        self._board = board

    async def run(self) -> None:
        """Публичная точка входа — пустой справочник/лок, затем сам опрос."""
        total = await StockAsset.objects.filter(
            is_active=True,
            board=self._board,
        ).acount()
        if total == 0:
            logger.info(
                "Опрос борда MOEX пропущен: нет ни одной активной бумаги, "
                "собирать нечего",
            )
            return

        try:
            async with redis_lock(
                redis_url=settings.REDIS_URL,
                key=BOARD_LOCK_KEY,
                ttl_seconds=settings.MOEX_BOARD_POLL_LOCK_TTL_SECONDS,
            ):
                await self._poll(total=total)
        except LockBusyError:
            logger.info("Опрос MOEX пропущен: предыдущий прогон ещё идёт (лок занят)")

    async def _poll(self, *, total: int) -> None:
        board = self._board
        logger.info(
            f"Опрос борда MOEX: активных бумаг {total}, запрашиваем борд {board}",
        )

        budget = settings.MOEX_BOARD_POLL_BUDGET_SECONDS
        deadline = asyncio.get_running_loop().time() + budget
        provider = MoexProvider(
            base_url=settings.MOEX_ISS_BASE_URL,
            default_board=board,
        )
        try:
            async with poll_budget_scope(
                deadline=deadline,
                budget_seconds=budget,
                label=f"опрос борда {board}",
                provider=provider,
            ):
                rows = await provider.get_board_snapshot(board)
        except ProviderConnectionError as exc:
            logger.warning(
                f"MOEX ISS недоступен: {describe_connection_failure(exc)} — "
                f"снимок борда за этот тик пропущен",
            )
            raise
        except PollBudgetExceededError as exc:
            logger.warning(
                f"MOEX ISS не ответил за бюджет прогона {budget} с"
                f"{last_failure_note(exc)} — снимок борда за этот тик пропущен",
            )
            raise
        finally:
            await provider.aclose()

        if not rows:
            logger.info(f"Борд {board}: ISS вернул пустой снимок (нет строк)")
            return

        trading_rows = [row for row in rows if row.is_trading]
        if not trading_rows:
            logger.info(
                f"Торги на борде закрыты (TRADINGSTATUS={rows[0].trading_status}), "
                f"снапшоты не пишем",
            )
            return

        latest_msk = max(row.timestamp for row in trading_rows).astimezone(MOSCOW_TZ)
        lag = (datetime.now(UTC) - latest_msk).total_seconds()
        logger.info(
            f"Борд {board}: {len(rows)} строк, время данных {latest_msk:%H:%M:%S} МСК "
            f"(лаг {lag:.0f} с)",
        )

        service = MoexBoardSnapshotService(board=board)
        result = await service.write_snapshots(rows)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Подготовлено к записи снапшотов: {result.written}, "
                f"пропущено (не торгуется): {result.skipped_not_trading}, "
                f"пропущено (нет активного актива): {result.skipped_unknown_asset}",
            )


async def poll_board() -> None:
    """Снимок цены борда MOEX по всем активным `StockAsset` этого борда."""
    await MoexBoardPoller(board=settings.MOEX_DEFAULT_BOARD).run()
