"""Юнит-тесты `BinanceRestClient` на замоканном HTTP-транспорте.

Используется встроенный `httpx.MockTransport` — httpx уже зависимость
проекта, отдельного `respx` не требуется: нужны только канонические
JSON-ответы по фиксированным путям/параметрам, без сложной маршрутизации
запросов, под которую заводился бы `respx`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import pytest

from tickfeeddmr.market_data.providers.base import PricePoint
from tickfeeddmr.market_data.providers.binance.rest import (
    BinanceRestClient,
    next_klines_cursor,
)
from tickfeeddmr.market_data.providers.exceptions import ProviderResponseError

if TYPE_CHECKING:
    from collections.abc import Callable

BASE_URL = "https://testnet.binance.example"


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> BinanceRestClient:
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url=BASE_URL, transport=transport)
    return BinanceRestClient(base_url=BASE_URL, client=async_client)


def _kline(
    *,
    close_price: str,
    volume: str,
    close_time_ms: int,
    open_time_ms: int = 0,
) -> list[object]:
    # [open_time, open, high, low, close, volume, close_time, ...] — хвост из
    # quote_asset_volume/trades/taker_buy_base/taker_buy_quote/ignore не нужен клиенту.
    return [
        open_time_ms,
        "0",
        "0",
        "0",
        close_price,
        volume,
        close_time_ms,
        "0",
        0,
        "0",
        "0",
        "0",
    ]


async def test_get_current_price_returns_price_point() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/ticker/price"
        assert request.url.params["symbol"] == "BTCUSDT"
        return httpx.Response(
            200,
            json={"symbol": "BTCUSDT", "price": "50123.45000000"},
        )

    client = _client(handler)
    point = await client.get_current_price("BTCUSDT")
    await client.aclose()

    assert point.trading_pair == "BTCUSDT"
    assert point.price == Decimal("50123.45000000")
    assert point.volume is None


async def test_get_current_price_raises_provider_error_on_bad_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(451, text="rate limited")

    client = _client(handler)
    try:
        with pytest.raises(ProviderResponseError):
            await client.get_current_price("BTCUSDT")
    finally:
        await client.aclose()


async def test_get_klines_parses_response_into_price_points() -> None:
    kline = _kline(
        close_price="50000.00",
        volume="1.23456789",
        close_time_ms=1_700_000_059_999,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/klines"
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "1m"
        return httpx.Response(200, json=[kline])

    client = _client(handler)
    points = await client.get_klines(
        "BTCUSDT",
        interval="1m",
        start_time=datetime(2023, 11, 14, tzinfo=UTC),
    )
    await client.aclose()

    assert points == [
        PricePoint(
            trading_pair="BTCUSDT",
            price=Decimal("50000.00"),
            volume=Decimal("1.23456789"),
            timestamp=datetime.fromtimestamp(1_700_000_059_999 / 1000, tz=UTC),
        ),
    ]


async def test_get_klines_omits_end_time_when_not_given() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "endTime" not in request.url.params
        return httpx.Response(200, json=[])

    client = _client(handler)
    points = await client.get_klines(
        "BTCUSDT",
        interval="1m",
        start_time=datetime(2023, 11, 14, tzinfo=UTC),
    )
    await client.aclose()

    assert points == []


async def test_get_klines_passes_end_time_when_given() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "endTime" in request.url.params
        return httpx.Response(200, json=[])

    client = _client(handler)
    await client.get_klines(
        "BTCUSDT",
        interval="1m",
        start_time=datetime(2023, 11, 14, tzinfo=UTC),
        end_time=datetime(2023, 11, 15, tzinfo=UTC),
    )
    await client.aclose()


async def test_get_klines_raises_provider_error_on_bad_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(451, text="rate limited")

    client = _client(handler)
    try:
        with pytest.raises(ProviderResponseError):
            await client.get_klines(
                "BTCUSDT",
                interval="1m",
                start_time=datetime(2023, 11, 14, tzinfo=UTC),
            )
    finally:
        await client.aclose()


def test_next_klines_cursor_is_one_millisecond_after_last_point() -> None:
    point = PricePoint(
        trading_pair="BTCUSDT",
        price=Decimal("1"),
        volume=None,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
    )

    cursor = next_klines_cursor(point)

    assert cursor == datetime(2024, 1, 1, 0, 0, 0, 1000, tzinfo=UTC)
