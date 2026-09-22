from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from redis.asyncio import Redis

from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow
from tickfeeddmr.market_data.services.moex_trade_stream import serialize_moex_trade
from tickfeeddmr.market_data.tests.api.sse_client import (
    open_sse_stream,
    parse_sse_chunk,
)

if TYPE_CHECKING:
    from django.test import AsyncRequestFactory
    from dmr.test import DMRAsyncClient
    from pytest_django.fixtures import Settings

    from tickfeeddmr.market_data.models import StockAsset

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("fast_stock_sse_settings"),
]

_TRADE_ID = 42
_QUANTITY = 150


async def test_all_requested_tickers_unknown_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/stocks/stream?secids=NOPE")

    assert response.status_code == HTTPStatus.NOT_FOUND
    detail = response.json()["detail"][0]["msg"]
    assert "Ни одна из запрошенных бумаг" in detail
    assert "NOPE" in detail


async def test_happy_path_published_trade_arrives_as_trade_event(
    dmr_async_client: DMRAsyncClient,
    dmr_async_rf: AsyncRequestFactory,
    stock_asset: StockAsset,
    settings: Settings,
) -> None:
    stock_asset.track_trades = True
    await stock_asset.asave(update_fields=["track_trades"])

    response = await open_sse_stream(
        dmr_async_client,
        dmr_async_rf,
        f"/api/stocks/stream?secids={stock_asset.symbol}",
    )
    assert response.status_code == HTTPStatus.OK

    agen = response.__aiter__()
    first_chunk = await asyncio.wait_for(agen.__anext__(), timeout=5)
    assert parse_sse_chunk(first_chunk)[0] == "heartbeat"

    redis_client: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    row = MoexTradeRow(
        trade_id=_TRADE_ID,
        price=Decimal("312.4"),
        quantity=_QUANTITY,
        side="buy",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        period="N",
    )
    try:
        await redis_client.xadd(
            settings.MOEX_TRADE_STREAM_KEY,
            serialize_moex_trade(stock_asset.symbol, row),
        )
    finally:
        await redis_client.aclose()

    try:
        second_chunk = await asyncio.wait_for(agen.__anext__(), timeout=5)
    finally:
        await agen.aclose()
    kind, body = parse_sse_chunk(second_chunk)

    assert kind == "trade"
    assert body["secid"] == stock_asset.symbol
    assert body["trade_id"] == _TRADE_ID
    assert Decimal(body["price"]) == row.price
    assert body["quantity"] == _QUANTITY
    assert body["side"] == "buy"
    assert body["data_delay_seconds"] > 0
