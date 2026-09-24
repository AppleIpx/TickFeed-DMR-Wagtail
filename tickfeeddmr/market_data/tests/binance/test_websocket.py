from __future__ import annotations

import asyncio
import itertools
import json
import logging
import time
from contextlib import asynccontextmanager, suppress
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from tickfeeddmr.market_data.providers.binance import websocket as binance_ws_module
from tickfeeddmr.market_data.providers.binance.websocket import (
    MAX_STREAMS_PER_CONNECTION,
    BinanceTradeStreamConsumer,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from websockets.asyncio.server import ServerConnection

    from tickfeeddmr.market_data.providers.base import TradeEvent

pytestmark = pytest.mark.usefixtures("fast_binance_ws_backoff")

ANEXT_TIMEOUT_SECONDS = 5
EXPECTED_BAD_PAYLOAD_COUNT = 2
EXPECTED_CONNECTION_COUNT = 2
AGG_TRADE_SYMBOL = "BTCUSDT"
AGG_TRADE_PRICE = "50000.10"
AGG_TRADE_QTY = "0.5"
AGG_TRADE_TIME_MS = 1_700_000_000_000


def _agg_trade_message(
    *,
    is_buyer_maker: bool = False,
    trade_id: int = 12345,
    symbol: str = AGG_TRADE_SYMBOL,
) -> str:
    return json.dumps(
        {
            "stream": f"{symbol.lower()}@aggTrade",
            "data": {
                "e": "aggTrade",
                "s": symbol,
                "p": AGG_TRADE_PRICE,
                "q": AGG_TRADE_QTY,
                "m": is_buyer_maker,
                "T": AGG_TRADE_TIME_MS,
                "a": trade_id,
            },
        },
    )


@asynccontextmanager
async def _serving(
    handler: Callable[[ServerConnection], Awaitable[None]],
) -> AsyncIterator[str]:
    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        yield f"ws://localhost:{port}"


def test_stream_url_joins_pairs_lowercased_with_agg_trade_suffix() -> None:
    consumer = BinanceTradeStreamConsumer(
        ws_base_url="wss://stream.binance.com:9443",
        trading_pairs=["BTCUSDT", "ETHUSDT"],
    )

    assert consumer.stream_url == (
        "wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade"
    )


async def test_stream_parses_agg_trade_and_maps_side() -> None:
    async def handler(connection: ServerConnection) -> None:
        await connection.send(_agg_trade_message(is_buyer_maker=True))
        await connection.wait_closed()

    async with _serving(handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        gen = consumer.stream()
        try:
            event = await asyncio.wait_for(anext(gen), timeout=ANEXT_TIMEOUT_SECONDS)
        finally:
            await gen.aclose()

    assert event.trading_pair == "BTCUSDT"
    assert event.price == Decimal("50000.10")
    assert event.volume == Decimal("0.5")
    assert event.side == "sell"
    assert event.trade_id == "12345"


async def test_stream_maps_buyer_maker_false_to_buy_side() -> None:
    async def handler(connection: ServerConnection) -> None:
        await connection.send(_agg_trade_message(is_buyer_maker=False))
        await connection.wait_closed()

    async with _serving(handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        gen = consumer.stream()
        try:
            event = await asyncio.wait_for(anext(gen), timeout=ANEXT_TIMEOUT_SECONDS)
        finally:
            await gen.aclose()

    assert event.side == "buy"


async def test_stream_skips_unexpected_payload_and_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(connection: ServerConnection) -> None:
        await connection.send(json.dumps({"stream": "btcusdt@depth"}))  # нет "data"
        await connection.send(json.dumps({"data": {"e": "trade"}}))  # чужой тип события
        await connection.send(_agg_trade_message())
        await connection.wait_closed()

    async with _serving(handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        gen = consumer.stream()
        try:
            with caplog.at_level(logging.WARNING):
                event = await asyncio.wait_for(
                    anext(gen),
                    timeout=ANEXT_TIMEOUT_SECONDS,
                )
        finally:
            await gen.aclose()

    assert event.trading_pair == "BTCUSDT"
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    unexpected_payload_warnings = sum(
        "Неожиданный формат сообщения Binance stream" in message for message in warnings
    )
    assert unexpected_payload_warnings == EXPECTED_BAD_PAYLOAD_COUNT


async def test_stream_skips_malformed_agg_trade_fields_without_reconnecting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Битое поле внутри уже опознанного aggTrade-payload не должно ронять сокет.

    Раньше `decimal.InvalidOperation`/`KeyError` из `_parse_message` не
    входили в `except (ConnectionClosed, OSError, JSONDecodeError)` вокруг
    цикла чтения и валили весь `stream()` — см. пробел A в
    `stream_binance_flow.md`.
    """
    connection_count = 0

    async def handler(connection: ServerConnection) -> None:
        nonlocal connection_count
        connection_count += 1
        malformed_price_message = json.dumps(
            {
                "stream": f"{AGG_TRADE_SYMBOL.lower()}@aggTrade",
                "data": {
                    "e": "aggTrade",
                    "s": AGG_TRADE_SYMBOL,
                    "p": "not-a-decimal",
                    "q": AGG_TRADE_QTY,
                    "m": False,
                    "T": AGG_TRADE_TIME_MS,
                    "a": 999,
                },
            },
        )
        missing_fields_message = json.dumps({"data": {"e": "aggTrade", "s": "BTCUSDT"}})
        await connection.send(malformed_price_message)
        await connection.send(missing_fields_message)  # KeyError на p/q/T/a
        await connection.send(_agg_trade_message(trade_id=1))
        await connection.wait_closed()

    async with _serving(handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        gen = consumer.stream()
        try:
            with caplog.at_level(logging.ERROR):
                event = await asyncio.wait_for(
                    anext(gen),
                    timeout=ANEXT_TIMEOUT_SECONDS,
                )
        finally:
            await gen.aclose()

    assert event.trade_id == "1"
    assert connection_count == 1

    errors = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    malformed_payload_errors = sum(
        "Битый payload aggTrade" in message for message in errors
    )
    assert malformed_payload_errors == EXPECTED_BAD_PAYLOAD_COUNT


async def test_stream_reconnects_after_abnormal_disconnect_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection_count = 0

    async def handler(connection: ServerConnection) -> None:
        nonlocal connection_count
        connection_count += 1
        if connection_count == 1:
            await connection.send(_agg_trade_message(trade_id=1))
            await asyncio.sleep(0.05)
            await connection.close(code=1011, reason="simulated abnormal disconnect")
        else:
            await connection.send(_agg_trade_message(trade_id=2))
            await connection.wait_closed()

    async with _serving(handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        gen = consumer.stream()
        try:
            with caplog.at_level(logging.INFO):
                first_event = await asyncio.wait_for(
                    anext(gen),
                    timeout=ANEXT_TIMEOUT_SECONDS,
                )
                second_event = await asyncio.wait_for(
                    anext(gen),
                    timeout=ANEXT_TIMEOUT_SECONDS,
                )
        finally:
            await gen.aclose()

    assert first_event.trade_id == "1"
    assert second_event.trade_id == "2"
    assert connection_count == EXPECTED_CONNECTION_COUNT

    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("разорвано" in message for message in warnings)

    infos = [r.message for r in caplog.records if r.levelno == logging.INFO]
    connected_infos = sum(
        "Подключение к Binance trade stream установлено" in message for message in infos
    )
    assert connected_infos == EXPECTED_CONNECTION_COUNT


type _Reply = Callable[[dict[str, Any]], dict[str, Any] | None]

THROTTLE_INTERVAL_SECONDS = 0.2
# Запас на планировщик: интервал меряется на стороне сервера.
THROTTLE_TOLERANCE_SECONDS = 0.05
QUIET_PERIOD_SECONDS = 0.1


def _acknowledge(message: dict[str, Any]) -> dict[str, Any]:
    return {"result": None, "id": message["id"]}


def _reject(message: dict[str, Any]) -> dict[str, Any]:
    return {"error": {"code": 2, "msg": "Invalid request"}, "id": message["id"]}


class _FakeBinance:
    """Двойник Binance: пути подключений, полученные управляющие сообщения
    (с моментом получения) и, опционально, ответы на них.
    """

    def __init__(self, *, reply: _Reply | None = None) -> None:
        self.paths: list[str] = []
        self.connections: list[ServerConnection] = []
        self.control: asyncio.Queue[tuple[float, dict[str, Any]]] = asyncio.Queue()
        self._reply = reply

    async def handler(self, connection: ServerConnection) -> None:
        self.paths.append(connection.request.path)
        self.connections.append(connection)
        with suppress(ConnectionClosed):
            async for raw_message in connection:
                message = json.loads(raw_message)
                await self.control.put((time.monotonic(), message))
                if self._reply is not None:
                    response = self._reply(message)
                    if response is not None:
                        await connection.send(json.dumps(response))

    async def next_control(self) -> dict[str, Any]:
        _received_at, message = await self.next_control_timed()
        return message

    async def next_control_timed(self) -> tuple[float, dict[str, Any]]:
        return await asyncio.wait_for(
            self.control.get(),
            timeout=ANEXT_TIMEOUT_SECONDS,
        )


def _path(*pairs: str) -> str:
    return "/stream?streams=" + "/".join(f"{pair.lower()}@aggTrade" for pair in pairs)


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(ANEXT_TIMEOUT_SECONDS):
        # Условие — чужое состояние (сервер, consumer), события на него нет.
        while not predicate():  # noqa: ASYNC110
            await asyncio.sleep(0.01)


async def _wait_connected(
    consumer: BinanceTradeStreamConsumer,
    server: _FakeBinance,
    *,
    count: int = 1,
) -> None:
    """Сервер принял `count`-е подключение, и клиент уже считает его своим."""
    await _wait_until(
        lambda: (
            len(server.paths) == count and consumer._connection is not None  # noqa: SLF001
        ),
    )


async def _next_event(events: asyncio.Queue[TradeEvent]) -> TradeEvent:
    return await asyncio.wait_for(events.get(), timeout=ANEXT_TIMEOUT_SECONDS)


@asynccontextmanager
async def _consuming(
    consumer: BinanceTradeStreamConsumer,
) -> AsyncIterator[asyncio.Queue[TradeEvent]]:
    """`consumer.stream()` в фоне — как `_pump_trades` в `stream_binance`."""
    events: asyncio.Queue[TradeEvent] = asyncio.Queue()

    async def pump() -> None:
        async for event in consumer.stream():
            await events.put(event)

    task = asyncio.create_task(pump())
    try:
        yield events
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [r.message for r in caplog.records if r.levelno == level]


@pytest.fixture(autouse=True)
def _no_control_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Троттлинг проверяется отдельным тестом, остальным он только мешает."""
    monkeypatch.setattr(binance_ws_module, "CONTROL_MESSAGE_MIN_INTERVAL_SECONDS", 0)


async def test_update_pairs_changes_subscriptions_without_reconnecting() -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        async with _consuming(consumer):
            await _wait_connected(consumer, server)
            await consumer.update_pairs(["BTCUSDT", "ETHUSDT"])
            first = await server.next_control()
            await consumer.update_pairs(["ETHUSDT", "SOLUSDT"])
            second = await server.next_control()
            third = await server.next_control()

    assert first == {"method": "SUBSCRIBE", "params": ["ethusdt@aggTrade"], "id": 1}
    # Сначала отписка, потом подписка; id растут на всё соединение.
    assert second == {
        "method": "UNSUBSCRIBE",
        "params": ["btcusdt@aggTrade"],
        "id": 2,
    }
    assert third == {"method": "SUBSCRIBE", "params": ["solusdt@aggTrade"], "id": 3}
    assert server.paths == [_path("BTCUSDT")]


async def test_update_pairs_with_same_set_sends_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        async with _consuming(consumer):
            await _wait_connected(consumer, server)
            with caplog.at_level(logging.INFO):
                await consumer.update_pairs(["BTCUSDT"])
            await asyncio.sleep(QUIET_PERIOD_SECONDS)

    assert server.control.empty()
    assert "Binance stream: подписки уже актуальны, менять нечего" in _messages(
        caplog,
        logging.INFO,
    )


async def test_subscription_ack_is_not_an_event_and_not_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance(reply=_acknowledge)
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        async with _consuming(consumer) as events:
            await _wait_connected(consumer, server)
            with caplog.at_level(logging.INFO):
                await consumer.update_pairs(["BTCUSDT", "ETHUSDT"])
                await server.next_control()
                # Ответ ушёл раньше сделки по тому же сокету: получив сделку,
                # знаем, что ответ уже разобран.
                await server.connections[0].send(
                    _agg_trade_message(symbol="ETHUSDT"),
                )
                event = await _next_event(events)

    assert event.trading_pair == "ETHUSDT"
    assert events.empty()
    assert _messages(caplog, logging.WARNING) == []
    assert (
        "Binance stream подтвердил SUBSCRIBE ['ethusdt@aggTrade'] (id=1)"
        in _messages(caplog, logging.INFO)
    )


async def test_subscription_error_is_logged_without_reconnecting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance(reply=_reject)
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        async with _consuming(consumer) as events:
            await _wait_connected(consumer, server)
            with caplog.at_level(logging.INFO):
                await consumer.update_pairs(["BTCUSDT", "ETHUSDT"])
                await server.next_control()
                await server.connections[0].send(_agg_trade_message())
                event = await _next_event(events)

    assert event.trading_pair == "BTCUSDT"
    assert server.paths == [_path("BTCUSDT")]
    errors = _messages(caplog, logging.ERROR)
    assert len(errors) == 1
    assert "отклонил SUBSCRIBE ['ethusdt@aggTrade'] (id=1)" in errors[0]
    assert _messages(caplog, logging.WARNING) == []


async def test_reconnect_after_disconnect_uses_current_pairs_in_url() -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        async with _consuming(consumer) as events:
            await _wait_connected(consumer, server)
            await consumer.update_pairs(["ETHUSDT", "BTCUSDT"])
            await server.next_control()

            await server.connections[0].close(code=1011, reason="simulated")
            await _wait_connected(consumer, server, count=2)
            await server.connections[1].send(_agg_trade_message())
            await _next_event(events)

    assert server.paths == [_path("BTCUSDT"), _path("BTCUSDT", "ETHUSDT")]
    # Новое соединение сразу с нужным набором — досылать подписки не нужно.
    assert server.control.empty()


async def test_update_pairs_without_connection_applies_on_connect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        with caplog.at_level(logging.INFO):
            await consumer.update_pairs(["ETHUSDT"])
        async with _consuming(consumer):
            await _wait_connected(consumer, server)

    assert server.paths == [_path("ETHUSDT")]
    assert server.control.empty()
    assert any(
        "соединения сейчас нет" in message and "ETHUSDT" in message
        for message in _messages(caplog, logging.INFO)
    )


async def test_empty_pairs_do_not_connect_until_update_and_empty_update_closes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(ws_base_url=base_url)
        with caplog.at_level(logging.INFO):
            async with _consuming(consumer):
                await asyncio.sleep(QUIET_PERIOD_SECONDS)
                assert server.paths == []

                await consumer.update_pairs(["BTCUSDT"])
                await _wait_connected(consumer, server)

                await consumer.update_pairs([])
                await asyncio.wait_for(
                    server.connections[0].wait_closed(),
                    timeout=ANEXT_TIMEOUT_SECONDS,
                )
                await asyncio.sleep(QUIET_PERIOD_SECONDS)
                assert len(server.paths) == 1

                await consumer.update_pairs(["ETHUSDT"])
                await _wait_connected(consumer, server, count=2)

    assert server.paths == [_path("BTCUSDT"), _path("ETHUSDT")]
    infos = _messages(caplog, logging.INFO)
    assert "Активных пар Binance не осталось, закрываем соединение" in infos
    assert any("Нет активных пар для Binance trade stream" in m for m in infos)
    # Своё закрытие — не обрыв.
    assert _messages(caplog, logging.WARNING) == []


async def test_control_messages_are_chunked_and_throttled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(binance_ws_module, "MAX_PARAMS_PER_REQUEST", 2)
    monkeypatch.setattr(
        binance_ws_module,
        "CONTROL_MESSAGE_MIN_INTERVAL_SECONDS",
        THROTTLE_INTERVAL_SECONDS,
    )
    new_pairs = ["B1USDT", "B2USDT", "B3USDT", "B4USDT", "B5USDT"]
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["AAAUSDT"],
        )
        async with _consuming(consumer):
            await _wait_connected(consumer, server)
            await consumer.update_pairs(["AAAUSDT", *new_pairs])
            received = [await server.next_control_timed() for _ in range(3)]

    assert [len(message["params"]) for _at, message in received] == [2, 2, 1]
    assert [p for _at, m in received for p in m["params"]] == [
        f"{pair.lower()}@aggTrade" for pair in new_pairs
    ]
    moments = [received_at for received_at, _message in received]
    gaps = [later - earlier for earlier, later in itertools.pairwise(moments)]
    assert all(
        gap >= THROTTLE_INTERVAL_SECONDS - THROTTLE_TOLERANCE_SECONDS for gap in gaps
    ), gaps


def test_pairs_above_connection_limit_are_capped_alphabetically(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pairs = [f"P{index:04d}" for index in range(MAX_STREAMS_PER_CONNECTION + 6)]

    with caplog.at_level(logging.ERROR):
        consumer = BinanceTradeStreamConsumer(
            ws_base_url="wss://unused.example",
            trading_pairs=list(reversed(pairs)),
        )

    streams = consumer.stream_url.split("streams=", 1)[1].split("/")
    assert streams == [
        f"{pair.lower()}@aggTrade" for pair in pairs[:MAX_STREAMS_PER_CONNECTION]
    ]
    errors = _messages(caplog, logging.ERROR)
    assert len(errors) == 1
    assert f"больше лимита {MAX_STREAMS_PER_CONNECTION}" in errors[0]


async def test_update_pairs_above_connection_limit_is_capped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pairs = [f"P{index:04d}" for index in range(MAX_STREAMS_PER_CONNECTION + 1)]
    consumer = BinanceTradeStreamConsumer(ws_base_url="wss://unused.example")

    with caplog.at_level(logging.ERROR):
        await consumer.update_pairs(pairs)

    assert consumer.stream_url.count("@aggTrade") == MAX_STREAMS_PER_CONNECTION
    assert f"p{MAX_STREAMS_PER_CONNECTION:04d}@aggTrade" not in consumer.stream_url
    assert len(_messages(caplog, logging.ERROR)) == 1


async def test_connection_closed_during_send_is_not_raised_and_reconnect_uses_new_set(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT"],
        )
        async with _consuming(consumer):
            await _wait_connected(consumer, server)
            monkeypatch.setattr(
                consumer._connection,  # noqa: SLF001
                "send",
                AsyncMock(side_effect=ConnectionClosedError(None, None)),
            )
            with caplog.at_level(logging.WARNING):
                await consumer.update_pairs(["BTCUSDT", "ETHUSDT"])

            await server.connections[0].close(code=1011, reason="simulated")
            await _wait_connected(consumer, server, count=2)

    assert server.paths == [_path("BTCUSDT"), _path("BTCUSDT", "ETHUSDT")]
    assert any(
        "Не удалось отправить подписку в Binance stream" in message
        for message in _messages(caplog, logging.WARNING)
    )


async def test_first_trade_is_logged_once_per_pair(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = _FakeBinance()
    async with _serving(server.handler) as base_url:
        consumer = BinanceTradeStreamConsumer(
            ws_base_url=base_url,
            trading_pairs=["BTCUSDT", "ETHUSDT"],
        )
        with caplog.at_level(logging.INFO):
            async with _consuming(consumer) as events:
                await _wait_connected(consumer, server)
                for trade_id, symbol in enumerate(["BTCUSDT", "BTCUSDT", "ETHUSDT"]):
                    await server.connections[0].send(
                        _agg_trade_message(symbol=symbol, trade_id=trade_id),
                    )
                    await _next_event(events)

                # Переподключение — не повод логировать снова.
                await server.connections[0].close(code=1011, reason="simulated")
                await _wait_connected(consumer, server, count=2)
                await server.connections[1].send(_agg_trade_message(trade_id=10))
                await _next_event(events)

                # А пара, убранная и добавленная заново, — повод.
                await consumer.update_pairs(["ETHUSDT"])
                await consumer.update_pairs(["BTCUSDT", "ETHUSDT"])
                await server.connections[1].send(_agg_trade_message(trade_id=11))
                await _next_event(events)

    infos = _messages(caplog, logging.INFO)
    btc_first = sum("первая сделка по BTCUSDT" in message for message in infos)
    eth_first = sum("первая сделка по ETHUSDT" in message for message in infos)
    assert (btc_first, eth_first) == (2, 1)
