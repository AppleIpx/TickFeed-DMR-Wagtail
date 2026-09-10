"""Юнит-тесты `BinanceProvider` с фейковым `BinanceRestClient`/`stream()`.

REST-слой замокан на уровне `BinanceRestClient` (через `rest_client=` —
провайдер принимает готовый клиент), а не через HTTP-транспорт: здесь
проверяется только склейка REST+WS в `BinanceProvider` (пагинация,
курсор, делегирование `stream()`), формат самих HTTP-ответов уже покрыт
`test_rest.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

from tickfeeddmr.market_data.providers.base import PricePoint, TradeEvent
from tickfeeddmr.market_data.providers.binance.provider import BinanceProvider
from tickfeeddmr.market_data.providers.binance.rest import (
    MAX_KLINES_LIMIT,
    BinanceRestClient,
    next_klines_cursor,
)

REST_BASE_URL = "https://unused.example"
WS_BASE_URL = "wss://unused.example"


def _point(pair: str, ts: datetime) -> PricePoint:
    return PricePoint(
        trading_pair=pair,
        price=Decimal("1"),
        volume=Decimal("1"),
        timestamp=ts,
    )


def _provider(rest_client: AsyncMock) -> BinanceProvider:
    return BinanceProvider(
        rest_base_url=REST_BASE_URL,
        ws_base_url=WS_BASE_URL,
        rest_client=rest_client,
    )


async def test_fetch_current_delegates_to_rest_client() -> None:
    rest_client = AsyncMock(spec=BinanceRestClient)
    expected = _point("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))
    rest_client.get_current_price.return_value = expected

    result = await _provider(rest_client).fetch_current("BTCUSDT")

    assert result is expected
    rest_client.get_current_price.assert_awaited_once_with("BTCUSDT")


async def test_fetch_history_yields_single_page_without_second_call() -> None:
    rest_client = AsyncMock(spec=BinanceRestClient)
    points = [_point("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))]
    rest_client.get_klines.return_value = points

    start = datetime(2024, 1, 1, tzinfo=UTC)
    collected = [
        p async for p in _provider(rest_client).fetch_history("BTCUSDT", start=start)
    ]

    assert collected == points
    rest_client.get_klines.assert_awaited_once_with(
        "BTCUSDT",
        interval="1m",
        start_time=start,
        end_time=None,
    )


async def test_fetch_history_stops_on_empty_first_page() -> None:
    rest_client = AsyncMock(spec=BinanceRestClient)
    rest_client.get_klines.return_value = []

    start = datetime(2024, 1, 1, tzinfo=UTC)
    collected = [
        p async for p in _provider(rest_client).fetch_history("BTCUSDT", start=start)
    ]

    assert collected == []
    rest_client.get_klines.assert_awaited_once()


async def test_fetch_history_paginates_when_page_is_full() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    first_page = [
        _point("BTCUSDT", start + timedelta(minutes=i)) for i in range(MAX_KLINES_LIMIT)
    ]
    second_page = [_point("BTCUSDT", start + timedelta(minutes=MAX_KLINES_LIMIT))]

    rest_client = AsyncMock(spec=BinanceRestClient)
    rest_client.get_klines.side_effect = [first_page, second_page]

    collected = [
        p async for p in _provider(rest_client).fetch_history("BTCUSDT", start=start)
    ]

    assert collected == [*first_page, *second_page]
    assert rest_client.get_klines.await_args_list == [
        call("BTCUSDT", interval="1m", start_time=start, end_time=None),
        call(
            "BTCUSDT",
            interval="1m",
            start_time=next_klines_cursor(first_page[-1]),
            end_time=None,
        ),
    ]


async def test_fetch_history_stops_once_cursor_reaches_end() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    first_page = [
        _point("BTCUSDT", start + timedelta(minutes=i)) for i in range(MAX_KLINES_LIMIT)
    ]
    end = next_klines_cursor(first_page[-1])

    rest_client = AsyncMock(spec=BinanceRestClient)
    rest_client.get_klines.return_value = first_page

    collected = [
        p
        async for p in _provider(rest_client).fetch_history(
            "BTCUSDT",
            start=start,
            end=end,
        )
    ]

    assert collected == first_page
    rest_client.get_klines.assert_awaited_once()


async def test_stream_delegates_to_trade_stream_consumer_and_forwards_events() -> None:
    event = TradeEvent(
        trading_pair="BTCUSDT",
        price=Decimal("1"),
        volume=Decimal("1"),
        side="buy",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        trade_id="1",
    )

    async def fake_stream() -> object:
        yield event

    with patch(
        "tickfeeddmr.market_data.providers.binance.provider.BinanceTradeStreamConsumer",
    ) as consumer_cls:
        consumer_cls.return_value.stream = MagicMock(return_value=fake_stream())

        provider = _provider(AsyncMock(spec=BinanceRestClient))
        collected = [e async for e in provider.stream(["BTCUSDT"])]

        consumer_cls.assert_called_once_with(
            ws_base_url=WS_BASE_URL,
            trading_pairs=["BTCUSDT"],
        )

    assert collected == [event]
