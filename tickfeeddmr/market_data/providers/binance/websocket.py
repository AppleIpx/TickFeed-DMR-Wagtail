from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, cast

import websockets
from websockets.exceptions import ConnectionClosed

from tickfeeddmr.market_data.providers.base import TradeEvent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Collection, Iterator, Sequence

    from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

STREAM_SUFFIX = "aggTrade"
STREAM_EVENT_TYPE = "aggTrade"
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2

MAX_STREAMS_PER_CONNECTION = 1024
MAX_PARAMS_PER_REQUEST = 200
CONTROL_MESSAGE_MIN_INTERVAL_SECONDS = 0.35

type ControlMethod = Literal["SUBSCRIBE", "UNSUBSCRIBE"]


def _stream_name(trading_pair: str) -> str:
    return f"{trading_pair.lower()}@{STREAM_SUFFIX}"


def _chunks(pairs: Sequence[str]) -> Iterator[Sequence[str]]:
    for start in range(0, len(pairs), MAX_PARAMS_PER_REQUEST):
        yield pairs[start : start + MAX_PARAMS_PER_REQUEST]


class BinanceTradeStreamConsumer:
    """Держит один сокет на комбинированный trade-стрим Binance.

    Живёт весь процесс: желаемый набор пар (`_desired`) переживает
    переподключения, подписки текущего соединения (`_subscribed`) — нет.
    """

    def __init__(
        self,
        *,
        ws_base_url: str,
        trading_pairs: Collection[str] = (),
    ) -> None:
        self._ws_base_url = ws_base_url
        self._desired: frozenset[str] = frozenset()
        self._subscribed: frozenset[str] = frozenset()
        self._connection: ClientConnection | None = None
        self._pairs_available = asyncio.Event()
        self._sync_lock = asyncio.Lock()
        self._next_request_id = 0
        self._pending_requests: dict[int, str] = {}
        self._last_control_sent_at: float | None = None
        self._awaiting_first_trade: set[str] = set()
        self._set_desired(trading_pairs)

    @property
    def stream_url(self) -> str:
        return self._url_for(self._desired)

    def _url_for(self, trading_pairs: frozenset[str]) -> str:
        streams = "/".join(_stream_name(pair) for pair in sorted(trading_pairs))
        return f"{self._ws_base_url}/stream?streams={streams}"

    async def update_pairs(self, trading_pairs: Collection[str]) -> None:
        """Выставить новый набор пар и довести до него открытое соединение.

        Обрыв соединения во время отправки не пробрасывается: `_desired`
        уже обновлён, переподключение возьмёт актуальный набор.
        """
        self._set_desired(trading_pairs)
        self._log_pending_diff()
        await self._sync_subscriptions()

    def _log_pending_diff(self) -> None:
        if self._connection is None:
            logger.info(
                f"Binance stream: соединения сейчас нет, набор пар "
                f"{sorted(self._desired)} применится при подключении",
            )
            return
        to_subscribe = sorted(self._desired - self._subscribed)
        to_unsubscribe = sorted(self._subscribed - self._desired)
        if not to_subscribe and not to_unsubscribe:
            logger.info("Binance stream: подписки уже актуальны, менять нечего")
            return
        logger.info(
            f"Binance stream: меняем подписки в открытом сокете — "
            f"добавить {to_subscribe}, убрать {to_unsubscribe}",
        )

    def _set_desired(self, trading_pairs: Collection[str]) -> None:
        pairs = frozenset(trading_pairs)
        if len(pairs) > MAX_STREAMS_PER_CONNECTION:
            logger.error(
                f"Активных пар Binance {len(pairs)} — больше лимита "
                f"{MAX_STREAMS_PER_CONNECTION} стримов на соединение, "
                f"подписываемся только на первые {MAX_STREAMS_PER_CONNECTION} "
                f"по алфавиту",
            )
            pairs = frozenset(sorted(pairs)[:MAX_STREAMS_PER_CONNECTION])
        self._awaiting_first_trade = (
            self._awaiting_first_trade | (pairs - self._desired)
        ) & pairs
        self._desired = pairs
        if pairs:
            self._pairs_available.set()
        else:
            self._pairs_available.clear()

    async def stream(self) -> AsyncGenerator[TradeEvent]:
        backoff = INITIAL_BACKOFF_SECONDS
        attempt = 0
        while True:
            if not self._desired:
                logger.info(
                    "Нет активных пар для Binance trade stream, ждём событий "
                    "об изменении CryptoAsset",
                )
                await self._pairs_available.wait()
                continue

            attempt += 1
            pairs = self._desired
            try:
                async with websockets.connect(self._url_for(pairs)) as connection:
                    logger.info(
                        f"Подключение к Binance trade stream установлено "
                        f"(пары={sorted(pairs)}, попытка={attempt})",
                    )
                    attempt = 0
                    backoff = INITIAL_BACKOFF_SECONDS
                    self._connection = connection
                    self._subscribed = pairs
                    await self._sync_subscriptions()
                    async for raw_message in connection:
                        event = self._parse_message(raw_message)
                        if event is not None:
                            if event.trading_pair in self._awaiting_first_trade:
                                self._awaiting_first_trade.discard(event.trading_pair)
                                logger.info(
                                    f"Binance stream: первая сделка по "
                                    f"{event.trading_pair} получена, данные идут",
                                )
                            yield event
            except (ConnectionClosed, OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"Соединение с Binance stream разорвано "
                    f"(попытка={attempt}, переподключение через {backoff:.1f}с): {exc}",
                )
            finally:
                self._connection = None
                self._subscribed = frozenset()
                self._pending_requests.clear()

            if not self._desired:
                continue
            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

    async def _sync_subscriptions(self) -> None:
        async with self._sync_lock:
            connection = self._connection
            if connection is None:
                return
            try:
                if not self._desired:
                    logger.info(
                        "Активных пар Binance не осталось, закрываем соединение",
                    )
                    await connection.close()
                    return
                changes: tuple[tuple[ControlMethod, frozenset[str]], ...] = (
                    ("UNSUBSCRIBE", self._subscribed - self._desired),
                    ("SUBSCRIBE", self._desired - self._subscribed),
                )
                for method, pairs in changes:
                    for chunk in _chunks(sorted(pairs)):
                        await self._send_control(connection, method, chunk)
                        if self._connection is not connection:
                            return
                        if method == "SUBSCRIBE":
                            self._subscribed |= frozenset(chunk)
                        else:
                            self._subscribed -= frozenset(chunk)
            except (ConnectionClosed, OSError) as exc:
                logger.warning(
                    f"Не удалось отправить подписку в Binance stream — соединение "
                    f"оборвалось, переподключение возьмёт актуальный набор пар: {exc}",
                )

    async def _send_control(
        self,
        connection: ClientConnection,
        method: ControlMethod,
        pairs: Sequence[str],
    ) -> None:
        await self._throttle_control()
        self._next_request_id += 1
        request_id = self._next_request_id
        streams = [_stream_name(pair) for pair in pairs]
        description = f"{method} {streams}"
        self._pending_requests[request_id] = description
        await connection.send(
            json.dumps({"method": method, "params": streams, "id": request_id}),
        )
        logger.info(f"Binance stream: отправлен {description} (id={request_id})")

    async def _throttle_control(self) -> None:
        if self._last_control_sent_at is not None:
            elapsed = time.monotonic() - self._last_control_sent_at
            if elapsed < CONTROL_MESSAGE_MIN_INTERVAL_SECONDS:
                await asyncio.sleep(CONTROL_MESSAGE_MIN_INTERVAL_SECONDS - elapsed)
        self._last_control_sent_at = time.monotonic()

    def _handle_control_response(self, envelope: dict[str, Any]) -> None:
        request_id = envelope["id"]
        description = self._pending_requests.pop(request_id, f"запрос id={request_id}")
        if envelope.get("error") is not None:
            logger.error(
                f"Binance stream отклонил {description} (id={request_id}): "
                f"{envelope['error']}",
            )
            return
        logger.info(f"Binance stream подтвердил {description} (id={request_id})")

    def _parse_message(self, raw_message: str | bytes) -> TradeEvent | None:
        envelope = json.loads(raw_message)
        if "id" in envelope and ("result" in envelope or "error" in envelope):
            self._handle_control_response(envelope)
            return None
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
            logger.exception(f"Битый payload aggTrade, пропускаем: {envelope}")
            return None
