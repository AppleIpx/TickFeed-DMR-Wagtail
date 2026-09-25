import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async
from redis.asyncio import Redis

from tickfeeddmr.market_data.providers.base import TradeEvent
from tickfeeddmr.market_data.services.trade_stream import serialize_trade_event
from tickfeeddmr.market_data.tests.api.sse_client import (
    collect_sse_events,
    next_non_heartbeat_chunk,
    open_sse_stream,
    parse_sse_chunk,
)
from tickfeeddmr.market_data.tests.factories import CryptoAssetFactory

if TYPE_CHECKING:
    from django.test import AsyncRequestFactory
    from dmr.test import DMRAsyncClient
    from pytest_django.fixtures import Settings

    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("fast_crypto_sse_settings"),
]


async def test_all_requested_tickers_unknown_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/crypto/stream?symbols=NOPE")

    assert response.status_code == HTTPStatus.NOT_FOUND
    detail = response.json()["detail"][0]["msg"]
    assert "Ни один из запрошенных тикеров не найден" in detail
    assert "NOPE" in detail


async def test_too_many_tickers_returns_422(
    dmr_async_client: DMRAsyncClient,
    settings: Settings,
) -> None:
    settings.MARKET_DATA_SSE_MAX_TICKERS = 2

    response = await dmr_async_client.get("/api/crypto/stream?symbols=A,B,C")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "Слишком много тикеров" in response.json()["detail"][0]["msg"]


async def test_partial_unknown_tickers_emits_warning_then_trades_for_known_only(
    dmr_async_client: DMRAsyncClient,
    dmr_async_rf: AsyncRequestFactory,
    crypto_asset: CryptoAsset,
) -> None:
    response = await open_sse_stream(
        dmr_async_client,
        dmr_async_rf,
        f"/api/crypto/stream?symbols={crypto_asset.symbol},NOPE",
    )

    assert response.status_code == HTTPStatus.OK
    (event,) = await collect_sse_events(response, count=1)
    kind, body = event

    assert kind == "warning"
    assert body["unknown"] == ["NOPE"]
    assert "NOPE" in body["detail"]
    assert crypto_asset.symbol in body["detail"]


async def test_happy_path_published_trade_arrives_as_trade_event(
    dmr_async_client: DMRAsyncClient,
    dmr_async_rf: AsyncRequestFactory,
    crypto_asset: CryptoAsset,
    settings: Settings,
) -> None:
    response = await open_sse_stream(
        dmr_async_client,
        dmr_async_rf,
        f"/api/crypto/stream?symbols={crypto_asset.symbol}",
    )
    assert response.status_code == HTTPStatus.OK

    agen = response.__aiter__()
    first_chunk = await asyncio.wait_for(agen.__anext__(), timeout=5)
    assert parse_sse_chunk(first_chunk)[0] == "heartbeat"

    redis_client: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    event = TradeEvent(
        trading_pair=crypto_asset.trading_pair,
        price=Decimal("50000.5"),
        volume=Decimal("0.25"),
        side="buy",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        trade_id="happy-1",
    )
    try:
        await redis_client.xadd(
            settings.MARKET_DATA_TRADE_STREAM_KEY,
            serialize_trade_event(event),
        )
    finally:
        await redis_client.aclose()

    try:
        kind, body = await next_non_heartbeat_chunk(agen)
    finally:
        await agen.aclose()

    assert kind == "trade"
    assert body["symbol"] == crypto_asset.symbol
    assert body["trade_id"] == "happy-1"
    assert Decimal(body["price"]) == event.price
    assert Decimal(body["volume"]) == event.volume
    assert body["side"] == "buy"
    assert body["data_delay_seconds"] == 0


async def test_unrequested_symbols_never_reach_the_stream(
    dmr_async_client: DMRAsyncClient,
    dmr_async_rf: AsyncRequestFactory,
    crypto_asset: CryptoAsset,
    settings: Settings,
) -> None:
    other_asset: CryptoAsset = await sync_to_async(CryptoAssetFactory.create)()

    response = await open_sse_stream(
        dmr_async_client,
        dmr_async_rf,
        f"/api/crypto/stream?symbols={crypto_asset.symbol}",
    )
    assert response.status_code == HTTPStatus.OK

    agen = response.__aiter__()
    first_chunk = await asyncio.wait_for(agen.__anext__(), timeout=5)
    assert parse_sse_chunk(first_chunk)[0] == "heartbeat"

    redis_client: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    unwanted = TradeEvent(
        trading_pair=other_asset.trading_pair,
        price=Decimal("1"),
        volume=Decimal("1"),
        side="sell",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        trade_id="unwanted-1",
    )
    wanted = TradeEvent(
        trading_pair=crypto_asset.trading_pair,
        price=Decimal("2"),
        volume=Decimal("2"),
        side="buy",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        trade_id="wanted-1",
    )
    try:
        await redis_client.xadd(
            settings.MARKET_DATA_TRADE_STREAM_KEY,
            serialize_trade_event(unwanted),
        )
        await redis_client.xadd(
            settings.MARKET_DATA_TRADE_STREAM_KEY,
            serialize_trade_event(wanted),
        )
    finally:
        await redis_client.aclose()

    try:
        kind, body = await next_non_heartbeat_chunk(agen)
    finally:
        await agen.aclose()

    assert kind == "trade"
    assert body["trade_id"] == "wanted-1"
