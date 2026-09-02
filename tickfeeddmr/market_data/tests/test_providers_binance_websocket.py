"""Юнит-тесты `BinanceTradeStreamConsumer` на локальном `websockets.serve`.

Реальный сокет на `localhost` — не мок HTTP-транспорта: `stream()` держит
постоянное WS-соединение и сам переподключается при обрыве, это поведение
(включая backoff/логирование) нельзя правдоподобно проверить без
настоящего (пусть и локального) сервера.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
import websockets

from tickfeeddmr.market_data.providers.binance import websocket as ws_module
from tickfeeddmr.market_data.providers.binance.websocket import (
    BinanceTradeStreamConsumer,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from websockets.asyncio.server import ServerConnection

ANEXT_TIMEOUT_SECONDS = 5
EXPECTED_BAD_PAYLOAD_COUNT = 2
EXPECTED_CONNECTION_COUNT = 2
AGG_TRADE_SYMBOL = "BTCUSDT"
AGG_TRADE_PRICE = "50000.10"
AGG_TRADE_QTY = "0.5"
AGG_TRADE_TIME_MS = 1_700_000_000_000


def _agg_trade_message(*, is_buyer_maker: bool = False, trade_id: int = 12345) -> str:
    return json.dumps(
        {
            "stream": f"{AGG_TRADE_SYMBOL.lower()}@aggTrade",
            "data": {
                "e": "aggTrade",
                "s": AGG_TRADE_SYMBOL,
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


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    # Реальный backoff (1s -> 30s) не нужен в тестах — реконнект должен
    # произойти как можно быстрее, само значение backoff здесь не проверяется.
    monkeypatch.setattr(ws_module, "INITIAL_BACKOFF_SECONDS", 0.01)
    monkeypatch.setattr(ws_module, "MAX_BACKOFF_SECONDS", 0.02)


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
        # Держим handler живым, пока клиент сам не закроет соединение (при
        # gen.aclose()) — иначе `websockets.serve()` зависает на выходе,
        # дожидаясь завершения этой корутины.
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
    assert event.side == "sell"  # is_buyer_maker=True -> "sell"
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
        "Unexpected Binance stream payload" in message for message in warnings
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
                    "p": "not-a-decimal",  # decimal.InvalidOperation
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
    assert connection_count == 1  # ни разу не переподключались

    errors = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    malformed_payload_errors = sum(
        "Malformed aggTrade payload" in message for message in errors
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
    assert any("disconnected" in message for message in warnings)

    infos = [r.message for r in caplog.records if r.levelno == logging.INFO]
    connected_infos = sum(
        "Connected to Binance trade stream" in message for message in infos
    )
    assert connected_infos == EXPECTED_CONNECTION_COUNT
