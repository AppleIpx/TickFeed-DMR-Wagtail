"""Юнит-тесты `poll_board`/`poll_trades` (`services/moex_polling/`).

`market_data/tasks.py` — тонкие `@shared_task`-обёртки над этими
функциями (`poll_moex_board`/`poll_moex_trades` только вызывают
`asyncio.run(poll_board())`/`asyncio.run(poll_trades())`), вся логика,
которую здесь проверяем, живёт в `services/moex_polling/{board,trades}.py`.

Требует реальную БД (`StockAsset`, см. `test_ingest.py`) и реальный Redis
для лока (`services/locks.py::redis_lock`) — тот же `settings.REDIS_URL`,
что и `pipeline/test_consume_market_data_stream.py`. `MoexProvider` мокается
на уровне класса — раздельно в `board.py`/`trades.py`, это два разных
импорта одного и того же класса, а не общий — чтобы проверить, что при
пустом справочнике/занятом локе провайдер вообще не создаётся — сеть не
трогается.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.conf import settings

from tickfeeddmr.market_data.services.locks import redis_lock
from tickfeeddmr.market_data.services.moex_polling import poll_board, poll_trades
from tickfeeddmr.market_data.services.moex_polling.board import BOARD_LOCK_KEY
from tickfeeddmr.market_data.services.moex_polling.trades import TRADES_LOCK_KEY

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import StockAsset

pytestmark = pytest.mark.django_db(transaction=True)

LOCK_TTL_SECONDS = 30
BOARD_PROVIDER_TARGET = (
    "tickfeeddmr.market_data.services.moex_polling.board.MoexProvider"
)
TRADES_PROVIDER_TARGET = (
    "tickfeeddmr.market_data.services.moex_polling.trades.MoexProvider"
)


async def test_poll_moex_board_skips_when_no_active_assets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch(BOARD_PROVIDER_TARGET) as provider_cls, caplog.at_level(logging.INFO):
        await poll_board()

    provider_cls.assert_not_called()
    assert any("собирать нечего" in r.message for r in caplog.records)


async def test_poll_moex_board_skips_when_lock_is_busy(
    caplog: pytest.LogCaptureFixture,
    stock_asset: StockAsset,
) -> None:
    async with redis_lock(
        redis_url=settings.REDIS_URL,
        key=BOARD_LOCK_KEY,
        ttl_seconds=LOCK_TTL_SECONDS,
    ):
        with (
            patch(BOARD_PROVIDER_TARGET) as provider_cls,
            caplog.at_level(logging.INFO),
        ):
            await poll_board()

    provider_cls.assert_not_called()
    assert any("лок занят" in r.message for r in caplog.records)


async def test_poll_moex_trades_skips_when_no_tracked_assets(
    caplog: pytest.LogCaptureFixture,
    stock_asset: StockAsset,  # track_trades=False по умолчанию у фабрики
) -> None:
    with patch(TRADES_PROVIDER_TARGET) as provider_cls, caplog.at_level(logging.INFO):
        await poll_trades()

    provider_cls.assert_not_called()
    assert any("собирать нечего" in r.message for r in caplog.records)


async def test_poll_moex_trades_skips_when_lock_is_busy(
    caplog: pytest.LogCaptureFixture,
    stock_asset: StockAsset,
) -> None:
    stock_asset.track_trades = True
    await stock_asset.asave(update_fields=["track_trades"])

    async with redis_lock(
        redis_url=settings.REDIS_URL,
        key=TRADES_LOCK_KEY,
        ttl_seconds=LOCK_TTL_SECONDS,
    ):
        with (
            patch(TRADES_PROVIDER_TARGET) as provider_cls,
            caplog.at_level(logging.INFO),
        ):
            await poll_trades()

    provider_cls.assert_not_called()
    assert any("лок занят" in r.message for r in caplog.records)
