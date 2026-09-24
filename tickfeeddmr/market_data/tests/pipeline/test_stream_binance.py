from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from asgiref.sync import sync_to_async
from django.db import DatabaseError
from redis.exceptions import ConnectionError as RedisConnectionError

from tickfeeddmr.market_data.management.commands import (
    stream_binance as stream_binance_module,
)
from tickfeeddmr.market_data.management.commands.stream_binance import (
    Command,
    _active_trading_pairs,
)
from tickfeeddmr.market_data.services import redis_retry
from tickfeeddmr.market_data.services.crypto_asset_changes import (
    CryptoAssetChange,
    serialize_crypto_asset_change,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.listener import (
    read_asset_changes,
    resolve_start_id,
)
from tickfeeddmr.market_data.tests.factories import CryptoAssetFactory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Collection

    from pytest_django.fixtures import Settings
    from redis.asyncio import Redis

WAIT_TIMEOUT_SECONDS = 5
# Несколько холостых `XREAD BLOCK` подряд — достаточно, чтобы увидеть лишнюю
# сверку, если бы она была.
READ_BLOCK_MS = 30
QUIET_PERIOD_SECONDS = 0.2
FAST_BACKOFF_SECONDS = 0.01
RECOVERY_REASON = "восстановление соединения с Redis"


def _changes_reason(count: int) -> str:
    return f"событий изменения CryptoAsset: {count}"


class _FakeConsumer:
    """Вместо `BinanceTradeStreamConsumer`: только запоминает наборы пар."""

    def __init__(self, calls: list[str] | None = None) -> None:
        self.updates: list[list[str]] = []
        self._calls = calls

    async def update_pairs(self, trading_pairs: Collection[str]) -> None:
        if self._calls is not None:
            self._calls.append("update_pairs")
        self.updates.append(sorted(trading_pairs))


class _RecordingCommand(Command):
    """`_reconcile` не ходит в БД — только запоминает причины сверок."""

    def __init__(self) -> None:
        super().__init__()
        self.reasons: list[str] = []

    async def _reconcile(self, consumer: Any, *, reason: str) -> None:
        self.reasons.append(reason)


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        # Условие — чужое состояние (сервер, consumer), события на него нет.
        while not predicate():  # noqa: ASYNC110
            await asyncio.sleep(0.01)


@asynccontextmanager
async def _watching(
    command: Command,
    consumer: _FakeConsumer,
    start_id: str,
) -> AsyncIterator[None]:
    task = asyncio.create_task(
        command._watch_asset_changes(consumer, start_id),  # type: ignore[arg-type]  # noqa: SLF001
    )
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    assert task.cancelled(), "наблюдатель завершился сам — упал раньше отмены"


async def _publish(redis_client: Redis, stream_key: str, trading_pair: str) -> str:
    change = CryptoAssetChange(
        asset_id=1,
        kind="updated",
        exchange="BINANCE",
        trading_pair=trading_pair,
    )
    return await redis_client.xadd(stream_key, serialize_crypto_asset_change(change))


@pytest.fixture(autouse=True)
def _fast_reads_and_backoff(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_BLOCK_MS = READ_BLOCK_MS
    monkeypatch.setattr(
        stream_binance_module,
        "INITIAL_BACKOFF_SECONDS",
        FAST_BACKOFF_SECONDS,
    )
    monkeypatch.setattr(redis_retry, "INITIAL_BACKOFF_SECONDS", FAST_BACKOFF_SECONDS)


# --- Старт `_run` --------------------------------------------------------------


def _patch_provider(
    monkeypatch: pytest.MonkeyPatch,
    consumer: _FakeConsumer,
) -> MagicMock:
    provider = MagicMock()
    provider.trade_stream.return_value = consumer
    provider.aclose = AsyncMock()
    monkeypatch.setattr(
        stream_binance_module,
        "BinanceProvider",
        MagicMock(return_value=provider),
    )
    return provider


class _StopError(Exception):
    pass


async def test_run_takes_start_id_before_reading_db_then_subscribes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    consumer = _FakeConsumer(calls)
    provider = _patch_provider(monkeypatch, consumer)

    async def fake_resolve_start_id(*_args: object) -> str:
        calls.append("resolve_start_id")
        return "5-0"

    async def fake_active_trading_pairs() -> list[str]:
        calls.append("read_db")
        return ["BTCUSDT"]

    watched_from: list[str] = []

    async def fake_watch(_self: Command, _consumer: object, start_id: str) -> None:
        watched_from.append(start_id)
        raise _StopError

    monkeypatch.setattr(
        stream_binance_module,
        "resolve_start_id",
        fake_resolve_start_id,
    )
    monkeypatch.setattr(
        stream_binance_module,
        "_active_trading_pairs",
        fake_active_trading_pairs,
    )
    monkeypatch.setattr(Command, "_pump_trades", AsyncMock())
    monkeypatch.setattr(Command, "_watch_asset_changes", fake_watch)

    with pytest.raises(ExceptionGroup) as excinfo:
        await Command()._run()  # noqa: SLF001

    assert excinfo.group_contains(_StopError)
    assert calls == ["resolve_start_id", "read_db", "update_pairs"]
    assert consumer.updates == [["BTCUSDT"]]
    assert watched_from == ["5-0"]
    provider.aclose.assert_awaited_once()


async def test_failure_in_one_task_cancels_the_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _patch_provider(monkeypatch, _FakeConsumer())
    monkeypatch.setattr(
        stream_binance_module,
        "resolve_start_id",
        AsyncMock(return_value="0-0"),
    )
    monkeypatch.setattr(
        stream_binance_module,
        "_active_trading_pairs",
        AsyncMock(return_value=[]),
    )
    watcher_started = asyncio.Event()
    watcher_cancelled = asyncio.Event()

    async def fake_watch(_self: Command, _consumer: object, _start_id: str) -> None:
        watcher_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            watcher_cancelled.set()
            raise

    async def failing_pump(_self: Command, _consumer: object) -> None:
        await watcher_started.wait()
        raise _StopError

    monkeypatch.setattr(Command, "_pump_trades", failing_pump)
    monkeypatch.setattr(Command, "_watch_asset_changes", fake_watch)

    with pytest.raises(ExceptionGroup) as excinfo:
        await asyncio.wait_for(Command()._run(), timeout=WAIT_TIMEOUT_SECONDS)  # noqa: SLF001

    assert excinfo.group_contains(_StopError)
    assert watcher_cancelled.is_set()
    provider.aclose.assert_awaited_once()


# --- `_watch_asset_changes` ----------------------------------------------------


async def test_batch_of_events_triggers_one_reconcile_and_advances_last_id(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    for pair in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        await _publish(redis_client, crypto_asset_changes_stream_key, pair)
    command = _RecordingCommand()

    async with _watching(command, _FakeConsumer(), "0-0"):
        await _wait_until(lambda: len(command.reasons) == 1)
        await asyncio.sleep(QUIET_PERIOD_SECONDS)
        # Прочитанная пачка не перечитывается — `last_id` сдвинулся.
        assert command.reasons == [_changes_reason(3)]

        await _publish(redis_client, crypto_asset_changes_stream_key, "XRPUSDT")
        await _wait_until(lambda: len(command.reasons) == 2)  # noqa: PLR2004
        await asyncio.sleep(QUIET_PERIOD_SECONDS)

    assert command.reasons == [_changes_reason(3), _changes_reason(1)]


async def test_events_up_to_start_id_are_not_reconciled_again(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    await _publish(redis_client, crypto_asset_changes_stream_key, "BTCUSDT")
    start_id = await resolve_start_id(redis_client, crypto_asset_changes_stream_key)
    command = _RecordingCommand()

    async with _watching(command, _FakeConsumer(), start_id):
        await asyncio.sleep(QUIET_PERIOD_SECONDS)

    assert command.reasons == []


async def test_database_error_retries_reconcile_before_moving_on(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    active_trading_pairs = AsyncMock(
        side_effect=[DatabaseError("simulated"), ["BTCUSDT"]],
    )
    monkeypatch.setattr(
        stream_binance_module,
        "_active_trading_pairs",
        active_trading_pairs,
    )
    await _publish(redis_client, crypto_asset_changes_stream_key, "BTCUSDT")
    consumer = _FakeConsumer()

    with caplog.at_level(logging.WARNING):
        async with _watching(Command(), consumer, "0-0"):
            await _wait_until(lambda: len(consumer.updates) == 1)
            await asyncio.sleep(QUIET_PERIOD_SECONDS)

    # Событие не потеряно и не перечитано: ровно одна успешная сверка.
    assert consumer.updates == [["BTCUSDT"]]
    assert active_trading_pairs.await_count == 2  # noqa: PLR2004
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("ошибка БД" in message for message in warnings)


async def test_redis_outage_resumes_from_last_id_and_reconciles_once_after(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_id = await _publish(redis_client, crypto_asset_changes_stream_key, "BTCUSDT")
    read_from: list[str] = []

    async def flaky_read(redis: Redis, **kwargs: Any) -> Any:
        read_from.append(kwargs["last_id"])
        if len(read_from) == 2:  # noqa: PLR2004
            msg = "simulated"
            raise RedisConnectionError(msg)
        return await read_asset_changes(redis, **kwargs)

    monkeypatch.setattr(stream_binance_module, "read_asset_changes", flaky_read)
    command = _RecordingCommand()

    async with _watching(command, _FakeConsumer(), "0-0"):
        await _wait_until(lambda: len(command.reasons) == 2)  # noqa: PLR2004
        await asyncio.sleep(QUIET_PERIOD_SECONDS)

    # Сверка после восстановления — одна, даже без новых событий.
    assert command.reasons == [_changes_reason(1), RECOVERY_REASON]
    assert read_from[0] == "0-0"
    assert set(read_from[1:]) == {first_id}


async def test_events_arriving_during_outage_give_one_reconcile_after_recovery(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_count = 0

    async def flaky_read(redis: Redis, **kwargs: Any) -> Any:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            await _publish(redis_client, crypto_asset_changes_stream_key, "BTCUSDT")
            msg = "simulated"
            raise RedisConnectionError(msg)
        return await read_asset_changes(redis, **kwargs)

    monkeypatch.setattr(stream_binance_module, "read_asset_changes", flaky_read)
    command = _RecordingCommand()

    async with _watching(command, _FakeConsumer(), "0-0"):
        await _wait_until(lambda: len(command.reasons) == 1)
        await asyncio.sleep(QUIET_PERIOD_SECONDS)

    assert command.reasons == [_changes_reason(1)]


# --- `_active_trading_pairs` ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_active_trading_pairs_reads_only_active_binance_pairs() -> None:
    await sync_to_async(CryptoAssetFactory.create)(trading_pair="BTCUSDT")
    await sync_to_async(CryptoAssetFactory.create)(
        trading_pair="ETHUSDT",
        is_active=False,
    )
    await sync_to_async(CryptoAssetFactory.create)(
        trading_pair="XRPUSDT",
        exchange="OTHER",
    )

    assert await _active_trading_pairs() == ["BTCUSDT"]
