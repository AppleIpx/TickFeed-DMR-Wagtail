"""Юнит-тесты `MoexProvider` с фейковым `MoexIssClient`.

По образцу `binance/test_provider.py`: HTTP-слой замокан на
уровне `MoexIssClient` (через `client=` — провайдер принимает готовый
клиент), формат самих ISS-ответов уже покрыт `test_client.py`.
Здесь проверяется склейка в `MoexProvider` — резолв `fetch_current` по
борду, пагинация свечей в `fetch_history`, курсор `stream()` и проброс
`get_board_snapshot`/`get_trades_page`, которыми реально пользуются
`market_data/tasks.py::poll_moex_board`/`poll_moex_trades`.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from tickfeeddmr.market_data.providers.exceptions import ProviderResponseError
from tickfeeddmr.market_data.providers.moex.client import MoexIssClient
from tickfeeddmr.market_data.providers.moex.provider import MoexProvider
from tickfeeddmr.market_data.providers.moex.types import (
    MoexBoardRow,
    MoexCandleRow,
    MoexTradeRow,
)

BASE_URL = "https://unused.example"
DEFAULT_BOARD = "TQBR"


def _board_row(secid: str, *, last: Decimal | None, volume: int | None) -> MoexBoardRow:
    return MoexBoardRow(
        secid=secid,
        last=last,
        open=None,
        high=None,
        low=None,
        change=None,
        change_percent=None,
        volume=volume,
        value=None,
        num_trades=None,
        timestamp=datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC),
        trading_status="T",
    )


def _provider(client: AsyncMock) -> MoexProvider:
    return MoexProvider(base_url=BASE_URL, default_board=DEFAULT_BOARD, client=client)


async def test_get_board_snapshot_delegates_to_client() -> None:
    client = AsyncMock(spec=MoexIssClient)
    expected = [_board_row("SBER", last=Decimal("250.55"), volume=100)]
    client.get_board_snapshot.return_value = expected

    result = await _provider(client).get_board_snapshot("TQBR")

    assert result is expected
    client.get_board_snapshot.assert_awaited_once_with("TQBR")


async def test_get_trades_page_delegates_to_client() -> None:
    client = AsyncMock(spec=MoexIssClient)
    expected: list[MoexTradeRow] = []
    client.get_trades_page.return_value = expected

    result = await _provider(client).get_trades_page("SBER", since_trade_no=1001)

    assert result is expected
    client.get_trades_page.assert_awaited_once_with("SBER", since_trade_no=1001)


async def test_fetch_current_returns_price_point_for_known_secid() -> None:
    client = AsyncMock(spec=MoexIssClient)
    client.get_board_snapshot.return_value = [
        _board_row("GAZP", last=Decimal("1"), volume=1),
        _board_row("SBER", last=Decimal("250.55"), volume=123_456),
    ]

    point = await _provider(client).fetch_current("SBER")

    assert point.trading_pair == "SBER"
    assert point.price == Decimal("250.55")
    assert point.volume == Decimal("123456")
    client.get_board_snapshot.assert_awaited_once_with(DEFAULT_BOARD)


async def test_fetch_current_raises_when_secid_not_on_board() -> None:
    client = AsyncMock(spec=MoexIssClient)
    client.get_board_snapshot.return_value = [
        _board_row("GAZP", last=Decimal("1"), volume=1),
    ]

    with pytest.raises(ProviderResponseError):
        await _provider(client).fetch_current("SBER")


async def test_fetch_current_raises_when_last_price_missing() -> None:
    client = AsyncMock(spec=MoexIssClient)
    client.get_board_snapshot.return_value = [
        _board_row("SBER", last=None, volume=None),
    ]

    with pytest.raises(ProviderResponseError):
        await _provider(client).fetch_current("SBER")


async def test_fetch_history_yields_single_page_without_second_call() -> None:
    candle = MoexCandleRow(
        open=Decimal("1"),
        high=Decimal("1"),
        low=Decimal("1"),
        close=Decimal("1.5"),
        value=Decimal("100"),
        volume=10,
        begin=datetime(2026, 9, 1, tzinfo=UTC),
        end=datetime(2026, 9, 2, tzinfo=UTC),
    )
    client = AsyncMock(spec=MoexIssClient)
    client.get_candles.return_value = [candle]

    start = datetime(2026, 9, 1, tzinfo=UTC)
    collected = [
        p async for p in _provider(client).fetch_history("SBER", start=start, end=start)
    ]

    assert len(collected) == 1
    assert collected[0].price == candle.close
    assert collected[0].timestamp == candle.end
    client.get_candles.assert_awaited_once()


async def test_fetch_history_stops_on_empty_page() -> None:
    client = AsyncMock(spec=MoexIssClient)
    client.get_candles.return_value = []

    start = datetime(2026, 9, 1, tzinfo=UTC)
    collected = [p async for p in _provider(client).fetch_history("SBER", start=start)]

    assert collected == []
    client.get_candles.assert_awaited_once()


async def test_stream_yields_trades_and_advances_cursor_per_pair() -> None:
    """`stream()` — поллинг-заглушка (см. докстринг `MoexProvider`), но её
    механика (курсор per pair, `since_trade_no`) всё равно стоит покрыть:
    `asyncio.sleep` между раундами замокан, чтобы не ждать реальные секунды,
    а второй вызов клиента поднимает управляемое исключение — единственный
    способ остановить бесконечный генератор снаружи.
    """
    row = MoexTradeRow(
        trade_id=1001,
        price=Decimal("250.55"),
        quantity=10,
        side="buy",
        timestamp=datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC),
        period="N",
    )
    client = AsyncMock(spec=MoexIssClient)
    client.get_trades_page.side_effect = [[row], _StreamStoppedError]

    events = []
    with (
        patch(
            "tickfeeddmr.market_data.providers.moex.provider.asyncio.sleep",
            new=AsyncMock(),
        ),
        contextlib.suppress(_StreamStoppedError),
    ):
        async for event in _provider(client).stream(["SBER"]):
            events.append(event)  # noqa: PERF401 -- нужны частично собранные events после исключения

    assert len(events) == 1
    assert events[0].trade_id == str(row.trade_id)
    assert events[0].side == "buy"
    assert client.get_trades_page.await_args_list[0].kwargs == {"since_trade_no": None}
    assert client.get_trades_page.await_args_list[1].kwargs == {
        "since_trade_no": row.trade_id,
    }


class _StreamStoppedError(Exception):
    """Останавливает бесконечный `stream()` после нужного числа сделок."""
