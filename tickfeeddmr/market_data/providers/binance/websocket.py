"""Постоянное WS-подключение к Binance combined trade stream.

https://developers.binance.com/en/docs/products/spot/web-socket-streams —
один сокет на все переданные торговые пары (`.../stream?streams=a@aggTrade/b@aggTrade`),
без REST-поллинга. При обрыве соединения переподключается с экспоненциальным
backoff, логируя каждую попытку — этого требует DoD этапа. Битое/пропущенное
поле внутри одного сообщения (не сам обрыв соединения) логируется и
пропускается в `_parse_message`, не вызывая переподключение.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, cast

import websockets
from websockets.exceptions import ConnectionClosed

from tickfeeddmr.market_data.providers.base import TradeEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

logger = logging.getLogger(__name__)

STREAM_SUFFIX = "aggTrade"
STREAM_EVENT_TYPE = "aggTrade"
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2


class BinanceTradeStreamConsumer:
    """Держит один сокет на комбинированный trade-стрим Binance."""

    def __init__(self, *, ws_base_url: str, trading_pairs: Sequence[str]) -> None:
        self._ws_base_url = ws_base_url
        self._trading_pairs = trading_pairs

    @property
    def stream_url(self) -> str:
        streams = "/".join(
            f"{pair.lower()}@{STREAM_SUFFIX}" for pair in self._trading_pairs
        )
        return f"{self._ws_base_url}/stream?streams={streams}"

    async def stream(self) -> AsyncIterator[TradeEvent]:
        backoff = INITIAL_BACKOFF_SECONDS
        attempt = 0
        while True:
            attempt += 1
            try:
                async with websockets.connect(self.stream_url) as connection:
                    logger.info(
                        f"Подключение к Binance trade stream установлено "
                        f"(пары={self._trading_pairs}, попытка={attempt})",
                    )
                    attempt = 0
                    backoff = INITIAL_BACKOFF_SECONDS
                    async for raw_message in connection:
                        event = self._parse_message(raw_message)
                        if event is not None:
                            yield event
            except (ConnectionClosed, OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"Соединение с Binance stream разорвано "
                    f"(попытка={attempt}, переподключение через {backoff:.1f}с): {exc}",
                )

            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> TradeEvent | None:
        envelope = json.loads(raw_message)
        payload = envelope.get("data")
        if payload is None or payload.get("e") != STREAM_EVENT_TYPE:
            logger.warning(
                f"Неожиданный формат сообщения Binance stream, пропускаем: {envelope}",
            )
            return None
        try:
            return TradeEvent(
                trading_pair=payload["s"],
                price=Decimal(payload["p"]),
                volume=Decimal(payload["q"]),
                side=cast("Literal['buy', 'sell']", "sell" if payload["m"] else "buy"),
                timestamp=datetime.fromtimestamp(payload["T"] / 1000, tz=UTC),
                trade_id=str(payload["a"]),
            )
        except Exception:
            # Сознательно широкий catch: битое/пропущенное поле внутри уже
            # опознанного aggTrade-payload (p/q/s/T/a) не должно рвать сокет и
            # ронять весь stream_binance — логируем и пропускаем именно это
            # сообщение, соединение остаётся открытым, счётчик переподключений
            # не растёт. Раньше KeyError/decimal.InvalidOperation отсюда
            # улетали наружу и валили весь процесс (см. stream_binance_flow.md).
            logger.exception(f"Битый payload aggTrade, пропускаем: {envelope}")
            return None
