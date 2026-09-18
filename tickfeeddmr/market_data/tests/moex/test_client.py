from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx
import pytest

from tickfeeddmr.market_data.providers import moex
from tickfeeddmr.market_data.providers.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
)
from tickfeeddmr.market_data.providers.moex.client import MAX_ATTEMPTS, MoexIssClient
from tickfeeddmr.market_data.providers.moex.types import MoexBoardRow, MoexTradeRow

if TYPE_CHECKING:
    from collections.abc import Callable

BASE_URL = "https://iss.testnet.example"


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    # Реальный backoff (1s -> 8s, до MAX_ATTEMPTS попыток) не нужен в
    # тестах — повторы должны отрабатывать как можно быстрее, само
    # значение backoff здесь не проверяется.
    monkeypatch.setattr(moex.client, "INITIAL_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(moex.client, "MAX_BACKOFF_SECONDS", 0.0)


BOARD_COLUMNS = [
    "SECID",
    "LAST",
    "LASTCHANGE",
    "LASTCHANGEPRCNT",
    "OPEN",
    "HIGH",
    "LOW",
    "VOLTODAY",
    "VALTODAY",
    "NUMTRADES",
    "UPDATETIME",
    "TRADINGSTATUS",
]

TRADES_COLUMNS = [
    "TRADENO",
    "TRADETIME",
    "PRICE",
    "QUANTITY",
    "VALUE",
    "PERIOD",
    "BUYSELL",
    "SYSTIME",
]

CANDLES_COLUMNS = ["open", "close", "high", "low", "value", "volume", "begin", "end"]


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> MoexIssClient:
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url=BASE_URL, transport=transport)
    return MoexIssClient(base_url=BASE_URL, client=async_client)


async def test_get_board_snapshot_parses_full_column_set() -> None:
    board_row = [
        "SBER",
        "250.55",
        "2.45",
        "0.98",
        "248.10",
        "252.30",
        "247.00",
        123_456,
        "30000000.00",
        4200,
        "12:44:28",
        "T",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == (
            "/iss/engines/stock/markets/shares/boards/TQBR/securities.json"
        )
        assert request.url.params["iss.only"] == "marketdata"
        return httpx.Response(
            200,
            json={"marketdata": {"columns": BOARD_COLUMNS, "data": [board_row]}},
        )

    client = _client(handler)
    with patch(
        "tickfeeddmr.market_data.providers.moex.client.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 9, 8, tzinfo=UTC)
        rows = await client.get_board_snapshot("TQBR")
    await client.aclose()

    assert rows == [
        MoexBoardRow(
            secid="SBER",
            last=Decimal("250.55"),
            open=Decimal("248.10"),
            high=Decimal("252.30"),
            low=Decimal("247.00"),
            change=Decimal("2.45"),
            change_percent=Decimal("0.98"),
            volume=123_456,
            value=Decimal("30000000.00"),
            num_trades=4200,
            timestamp=datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC),
            trading_status="T",
        ),
    ]
    assert rows[0].is_trading is True


@pytest.mark.parametrize("status", ["T", "L", "E"])
async def test_get_board_snapshot_active_trading_statuses_are_trading(
    status: str,
) -> None:
    board_row = [
        "SBER",
        "250.55",
        None,
        None,
        "248.10",
        "252.30",
        "247.00",
        123_456,
        "30000000.00",
        4200,
        "18:50:00",
        status,
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"marketdata": {"columns": BOARD_COLUMNS, "data": [board_row]}},
        )

    client = _client(handler)
    rows = await client.get_board_snapshot("TQBR")
    await client.aclose()

    assert rows[0].trading_status == status
    assert rows[0].is_trading is True


async def test_get_board_snapshot_trading_status_not_t_is_not_trading() -> None:
    board_row = [
        "SBER",
        "250.55",
        None,
        None,
        "248.10",
        "252.30",
        "247.00",
        123_456,
        "30000000.00",
        4200,
        "18:50:00",
        "C",  # торги закрыты
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"marketdata": {"columns": BOARD_COLUMNS, "data": [board_row]}},
        )

    client = _client(handler)
    rows = await client.get_board_snapshot("TQBR")
    await client.aclose()

    assert rows[0].trading_status == "C"
    assert rows[0].is_trading is False


async def test_get_board_snapshot_empty_data_on_non_trading_day() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"marketdata": {"columns": BOARD_COLUMNS, "data": []}},
        )

    client = _client(handler)
    rows = await client.get_board_snapshot("TQBR")
    await client.aclose()

    assert rows == []


async def test_get_board_snapshot_raises_connection_error_retries_exhausted() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, text="boom")

    client = _client(handler)
    try:
        with pytest.raises(ProviderConnectionError) as exc_info:
            await client.get_board_snapshot("TQBR")
    finally:
        await client.aclose()

    assert call_count == MAX_ATTEMPTS
    assert exc_info.value.attempts == MAX_ATTEMPTS


async def test_get_trades_page_first_page_without_cursor() -> None:
    trade_row = [
        1001,
        "12:44:28",
        "250.55",
        10,
        "2505.50",
        "N",
        "B",
        "2026-09-08 12:44:28",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == (
            "/iss/engines/stock/markets/shares/securities/SBER/trades.json"
        )
        assert "tradeno" not in request.url.params
        assert "next_trade" not in request.url.params
        return httpx.Response(
            200,
            json={"trades": {"columns": TRADES_COLUMNS, "data": [trade_row]}},
        )

    client = _client(handler)
    rows = await client.get_trades_page("SBER")
    await client.aclose()

    assert rows == [
        MoexTradeRow(
            trade_id=1001,
            price=Decimal("250.55"),
            quantity=10,
            side="buy",
            timestamp=datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC),
            period="N",
        ),
    ]


async def test_get_trades_page_with_cursor_requests_next_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["tradeno"] == "1001"
        assert request.url.params["next_trade"] == "1"
        return httpx.Response(
            200,
            json={"trades": {"columns": TRADES_COLUMNS, "data": []}},
        )

    client = _client(handler)
    rows = await client.get_trades_page("SBER", since_trade_no=1001)
    await client.aclose()

    assert rows == []


async def test_get_trades_page_sell_side() -> None:
    trade_row = [
        1002,
        "12:44:29",
        "250.60",
        5,
        "1253.00",
        "N",
        "S",
        "2026-09-08 12:44:29",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"trades": {"columns": TRADES_COLUMNS, "data": [trade_row]}},
        )

    client = _client(handler)
    rows = await client.get_trades_page("SBER")
    await client.aclose()

    assert rows[0].side == "sell"


async def test_get_trades_page_raises_connection_error_retries_exhausted() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(502, text="bad gateway")

    client = _client(handler)
    try:
        with pytest.raises(ProviderConnectionError) as exc_info:
            await client.get_trades_page("SBER")
    finally:
        await client.aclose()

    assert call_count == MAX_ATTEMPTS
    assert exc_info.value.attempts == MAX_ATTEMPTS


BORDERS_COLUMNS = ["interval", "begin", "end"]


async def test_get_candle_borders_returns_first_and_last_date_for_interval() -> None:
    borders_data = [
        [1, "2020-01-01 00:00:00", "2026-09-08 23:59:59"],
        [24, "2007-05-11 00:00:00", "2026-09-08 00:00:00"],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == (
            "/iss/engines/stock/markets/shares/securities/SBER/candleborders.json"
        )
        return httpx.Response(
            200,
            json={"borders": {"columns": BORDERS_COLUMNS, "data": borders_data}},
        )

    client = _client(handler)
    first, last = await client.get_candle_borders("SBER", interval="24")
    await client.aclose()

    assert first == date(2007, 5, 11)
    assert last == date(2026, 9, 8)


async def test_get_candle_borders_raises_response_error_when_interval_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "borders": {
                    "columns": BORDERS_COLUMNS,
                    "data": [[1, "2020-01-01 00:00:00", "2026-09-08 23:59:59"]],
                },
            },
        )

    client = _client(handler)
    try:
        with pytest.raises(ProviderResponseError):
            await client.get_candle_borders("SBER", interval="24")
    finally:
        await client.aclose()


async def test_get_candle_borders_raises_connection_error_retries_exhausted() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, text="boom")

    client = _client(handler)
    try:
        with pytest.raises(ProviderConnectionError) as exc_info:
            await client.get_candle_borders("SBER", interval="24")
    finally:
        await client.aclose()

    assert call_count == MAX_ATTEMPTS
    assert exc_info.value.attempts == MAX_ATTEMPTS


CANDLE_VOLUME = 123_456


async def test_get_candles_parses_response() -> None:
    candle_row = [
        "248.10",
        "250.55",
        "252.30",
        "247.00",
        "30000000.00",
        CANDLE_VOLUME,
        "2026-09-08 00:00:00",
        "2026-09-08 23:59:59",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == (
            "/iss/engines/stock/markets/shares/securities/SBER/candles.json"
        )
        assert request.url.params["interval"] == "1"
        assert request.url.params["from"] == "2026-09-01"
        return httpx.Response(
            200,
            json={"candles": {"columns": CANDLES_COLUMNS, "data": [candle_row]}},
        )

    client = _client(handler)
    candles = await client.get_candles(
        "SBER",
        start=datetime(2026, 9, 1, tzinfo=UTC),
        end=None,
        interval="1",
    )
    await client.aclose()

    assert candles[0].open == Decimal("248.10")
    assert candles[0].close == Decimal("250.55")
    assert candles[0].high == Decimal("252.30")
    assert candles[0].low == Decimal("247.00")
    assert candles[0].volume == CANDLE_VOLUME
    assert candles[0].begin == datetime(2026, 9, 7, 21, 0, 0, tzinfo=UTC)
    assert candles[0].end == datetime(2026, 9, 8, 20, 59, 59, tzinfo=UTC)


async def test_get_candles_raises_connection_error_retries_exhausted() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, text="boom")

    client = _client(handler)
    try:
        with pytest.raises(ProviderConnectionError) as exc_info:
            await client.get_candles(
                "SBER",
                start=datetime(2026, 9, 1, tzinfo=UTC),
                end=None,
                interval="1",
            )
    finally:
        await client.aclose()

    assert call_count == MAX_ATTEMPTS
    assert exc_info.value.attempts == MAX_ATTEMPTS
