import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.conf import settings

from tickfeeddmr.market_data.management.commands.consume_market_data_stream import (
    NEW_ENTRIES_ID,
    Command,
)
from tickfeeddmr.market_data.models import CryptoPriceSnapshot
from tickfeeddmr.market_data.providers.base import TradeEvent
from tickfeeddmr.market_data.providers.binance import EXCHANGE
from tickfeeddmr.market_data.services.ingest import CryptoTradeIngestService
from tickfeeddmr.market_data.services.trade_stream import serialize_trade_event

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings
    from redis.asyncio import Redis

    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = pytest.mark.django_db(transaction=True)

DELIVER_ALL_COUNT = 1000


async def _snapshot_exists(**filters: object) -> bool:
    # Тесты здесь `async def` (нужен event loop для `_recover_pending`), а
    # Django ORM в async-контексте без `sync_to_async` бросает
    # `SynchronousOnlyOperation` — как и в проде (`ingest.write_snapshots`
    # тоже вызывается только через `sync_to_async`, см. `_process_batch`).
    return await sync_to_async(CryptoPriceSnapshot.objects.filter(**filters).exists)()


async def _snapshot_count(**filters: object) -> int:
    return await sync_to_async(CryptoPriceSnapshot.objects.filter(**filters).count)()


def _event(*, trading_pair: str, trade_id: str) -> TradeEvent:
    return TradeEvent(
        trading_pair=trading_pair,
        price=Decimal("123.45"),
        volume=Decimal("0.1"),
        side="buy",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        trade_id=trade_id,
    )


@pytest.fixture
def group_name(settings: Settings) -> str:
    name = f"test-market-data-consumers-{uuid.uuid4()}"
    settings.MARKET_DATA_TRADE_CONSUMER_GROUP = name
    return name


@pytest.fixture
async def command(
    redis_client: Redis,
    consumer_stream_key: str,
    group_name: str,
) -> Command:
    """`Command`, уже создавший consumer group — как после `_ensure_group` в `_run`."""
    instance = Command()
    await instance._ensure_group(redis_client)  # noqa: SLF001
    return instance


async def _deliver_without_ack(
    redis_client: Redis,
    *,
    consumer_stream_key: str,
    group_name: str,
    consumer_name: str,
    fields_list: list[dict[str, str]],
) -> None:
    """`XADD` каждого сообщения + один `XREADGROUP ... >` без `XACK`.

    Эмулирует падение процесса между чтением новых сообщений и ack —
    все сообщения доставляются `consumer_name` и оседают в его PEL.
    """
    for fields in fields_list:
        await redis_client.xadd(consumer_stream_key, fields)
    await redis_client.xreadgroup(
        groupname=group_name,
        consumername=consumer_name,
        streams={consumer_stream_key: NEW_ENTRIES_ID},
        count=DELIVER_ALL_COUNT,
    )


async def test_recover_pending_processes_and_acks_previously_undelivered_messages(
    redis_client: Redis,
    consumer_stream_key: str,
    group_name: str,
    command: Command,
    crypto_asset: CryptoAsset,
) -> None:
    event = _event(trading_pair=crypto_asset.trading_pair, trade_id="pel-1")
    await _deliver_without_ack(
        redis_client,
        consumer_stream_key=consumer_stream_key,
        group_name=group_name,
        consumer_name=settings.MARKET_DATA_TRADE_CONSUMER_NAME,
        fields_list=[serialize_trade_event(event)],
    )

    ingest = CryptoTradeIngestService(exchange=EXCHANGE)
    with patch.object(ingest, "write_snapshots", wraps=ingest.write_snapshots) as spy:
        await command._recover_pending(redis_client, ingest)  # noqa: SLF001

    spy.assert_called_once()
    (recovered_events,) = spy.call_args.args
    assert [e.trade_id for e in recovered_events] == ["pel-1"]

    pending_summary = await redis_client.xpending(consumer_stream_key, group_name)
    assert pending_summary["pending"] == 0

    assert await _snapshot_exists(
        asset=crypto_asset,
        price=event.price,
        volume=event.volume,
    )


async def test_recover_pending_is_a_no_op_when_pel_is_empty(
    redis_client: Redis,
    consumer_stream_key: str,
    group_name: str,
    command: Command,
) -> None:
    ingest = CryptoTradeIngestService(exchange=EXCHANGE)
    with patch.object(ingest, "write_snapshots", wraps=ingest.write_snapshots) as spy:
        await command._recover_pending(redis_client, ingest)  # noqa: SLF001

    spy.assert_not_called()
    pending_summary = await redis_client.xpending(consumer_stream_key, group_name)
    assert pending_summary["pending"] == 0


async def test_recover_pending_paginates_over_read_count_sized_batches(  # noqa: PLR0913, PLR0917
    settings: Settings,
    redis_client: Redis,
    consumer_stream_key: str,
    group_name: str,
    command: Command,
    crypto_asset: CryptoAsset,
) -> None:
    settings.MARKET_DATA_TRADE_READ_COUNT = 2
    events = [
        _event(trading_pair=crypto_asset.trading_pair, trade_id=f"pel-{i}")
        for i in range(5)
    ]
    await _deliver_without_ack(
        redis_client,
        consumer_stream_key=consumer_stream_key,
        group_name=group_name,
        consumer_name=settings.MARKET_DATA_TRADE_CONSUMER_NAME,
        fields_list=[serialize_trade_event(event) for event in events],
    )

    ingest = CryptoTradeIngestService(exchange=EXCHANGE)
    with patch.object(ingest, "write_snapshots", wraps=ingest.write_snapshots) as spy:
        await command._recover_pending(redis_client, ingest)  # noqa: SLF001

    # MARKET_DATA_TRADE_READ_COUNT=2 на 5 сообщений -> минимум 3 отдельных батча/вызова.
    min_expected_batches = 3
    assert spy.call_count >= min_expected_batches
    recovered_trade_ids = {
        recovered_event.trade_id
        for call in spy.call_args_list
        for recovered_event in call.args[0]
    }
    assert recovered_trade_ids == {event.trade_id for event in events}

    pending_summary = await redis_client.xpending(consumer_stream_key, group_name)
    assert pending_summary["pending"] == 0
    assert await _snapshot_count(asset=crypto_asset) == len(events)


async def test_recover_pending_skips_malformed_message_but_still_acks_it(
    caplog: pytest.LogCaptureFixture,
    redis_client: Redis,
    consumer_stream_key: str,
    group_name: str,
    command: Command,
) -> None:
    await _deliver_without_ack(
        redis_client,
        consumer_stream_key=consumer_stream_key,
        group_name=group_name,
        consumer_name=settings.MARKET_DATA_TRADE_CONSUMER_NAME,
        fields_list=[
            {"trading_pair": "BTCUSDT"},
        ],
    )

    ingest = CryptoTradeIngestService(exchange=EXCHANGE)
    with (
        patch.object(ingest, "write_snapshots", wraps=ingest.write_snapshots) as spy,
        caplog.at_level(logging.ERROR),
    ):
        await command._recover_pending(redis_client, ingest)  # noqa: SLF001

    spy.assert_called_once_with([])
    assert any("Битая запись сделки в стриме" in r.message for r in caplog.records)

    pending_summary = await redis_client.xpending(consumer_stream_key, group_name)
    assert pending_summary["pending"] == 0
    assert not await _snapshot_exists()
