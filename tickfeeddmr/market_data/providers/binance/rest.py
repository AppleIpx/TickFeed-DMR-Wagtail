import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx
from django.conf import settings

from tickfeeddmr.market_data.providers.base import PricePoint
from tickfeeddmr.market_data.providers.binance.types import BinanceCandleRow
from tickfeeddmr.market_data.providers.http_retry import RetryingHttpClient, RetryPolicy

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

KLINES_PATH = "/api/v3/klines"
TICKER_PRICE_PATH = "/api/v3/ticker/price"
MAX_KLINES_LIMIT = 1000
CONNECT_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0

MAX_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0
BACKOFF_MULTIPLIER = 2
BACKOFF_JITTER = 0.2

# 429 — Binance-лимиты запросов (задокументированы жёстче, чем у ISS —
# отсюда меньше `MAX_ATTEMPTS`, чем у `MoexIssClient`); 500-504 — временные
# проблемы на стороне Binance.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_NON_RETRYABLE_TRANSPORT_ERRORS: tuple[type[httpx.TransportError], ...] = (
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
    httpx.ProxyError,
)
_NON_RETRYABLE_CAUSES: tuple[type[BaseException], ...] = ()

ERROR_REASON_MAX_CHARS = 200

# Дневная свеча `klines` с `timeZone=3` выровнена на московские сутки —
# проверено живым запросом (`GET /api/v3/klines?...&timeZone=3`, начало
# свечи 00:00 МСК). Тот же часовой пояс, что у MOEX/ЦБ: доменный день
# везде считается по Москве (см. `settings.MOSCOW_TZ`).
MOSCOW_TZ = settings.MOSCOW_TZ
DAILY_CANDLE_INTERVAL = "1d"
DAILY_CANDLE_TIME_ZONE = "3"


class BinanceRestClient:
    """Клиент к REST-эндпоинтам Binance: `klines` и `ticker/price`.

    Все запросы идут через общий `RetryingHttpClient` (повторы с backoff на
    сетевых сбоях и статусах 429/500/502/503/504, как у `MoexIssClient`/
    `CbrDailyRatesClient`) — нормализация ответа в `PricePoint`/
    `BinanceCandleRow`, пагинация истории и выбор эндпоинта остаются на
    стороне `BinanceProvider`/вызывающего сервиса.
    """

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._http = RetryingHttpClient(
            base_url=base_url,
            client=client,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            request_timeout=REQUEST_TIMEOUT_SECONDS,
            logger=logger,
        )

    @property
    def last_failure_reason(self) -> str | None:
        """Причина последней неудачной попытки текущего (или последнего) запроса."""
        return self._http.last_failure_reason

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_current_price(self, trading_pair: str) -> PricePoint:
        response = await self._get(
            TICKER_PRICE_PATH,
            params={"symbol": trading_pair},
        )
        payload = response.json()
        return PricePoint(
            trading_pair=trading_pair,
            price=Decimal(payload["price"]),
            volume=None,
            timestamp=datetime.now(UTC),
        )

    async def get_klines(
        self,
        trading_pair: str,
        *,
        interval: str,
        start_time: datetime,
        end_time: datetime | None = None,
        limit: int = MAX_KLINES_LIMIT,
    ) -> Sequence[PricePoint]:
        params: dict[str, Any] = {
            "symbol": trading_pair,
            "interval": interval,
            "startTime": int(start_time.timestamp() * 1000),
            "limit": min(limit, MAX_KLINES_LIMIT),
        }
        if end_time is not None:
            params["endTime"] = int(end_time.timestamp() * 1000)

        response = await self._get(KLINES_PATH, params=params)
        return [
            self._kline_to_price_point(trading_pair, kline) for kline in response.json()
        ]

    async def get_daily_candles(
        self,
        trading_pair: str,
        *,
        start_time: datetime,
        end_time: datetime | None = None,
        limit: int = MAX_KLINES_LIMIT,
    ) -> Sequence[BinanceCandleRow]:
        """Одна страница дневных свечей (`interval=1d`, день по МСК).

        Постраничность нескольких вызовов (полная история актива может
        превышать `MAX_KLINES_LIMIT`) — на вызывающем коде
        (`services/daily_candles/crypto.py`), по аналогии с тем, как
        `MoexIssClient.get_candles` не пагинирует сама себя.
        """
        params: dict[str, Any] = {
            "symbol": trading_pair,
            "interval": DAILY_CANDLE_INTERVAL,
            "timeZone": DAILY_CANDLE_TIME_ZONE,
            "startTime": int(start_time.timestamp() * 1000),
            "limit": min(limit, MAX_KLINES_LIMIT),
        }
        if end_time is not None:
            params["endTime"] = int(end_time.timestamp() * 1000)

        response = await self._get(KLINES_PATH, params=params)
        return [self._kline_to_candle_row(kline) for kline in response.json()]

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any],
    ) -> httpx.Response:
        policy = RetryPolicy(
            max_attempts=MAX_ATTEMPTS,
            initial_backoff_seconds=INITIAL_BACKOFF_SECONDS,
            max_backoff_seconds=MAX_BACKOFF_SECONDS,
            backoff_multiplier=BACKOFF_MULTIPLIER,
            backoff_jitter=BACKOFF_JITTER,
            retryable_status_codes=RETRYABLE_STATUS_CODES,
            non_retryable_transport_errors=_NON_RETRYABLE_TRANSPORT_ERRORS,
            non_retryable_causes=_NON_RETRYABLE_CAUSES,
            error_reason_max_chars=ERROR_REASON_MAX_CHARS,
            log_label="Binance REST",
            error_label="Binance REST",
        )
        return await self._http.get(path, params=params, policy=policy)

    @staticmethod
    def _kline_to_price_point(trading_pair: str, kline: list[Any]) -> PricePoint:
        # Свеча Binance: [open_time, open, high, low, close, volume, close_time, ...].
        close_price_index = 4
        volume_index = 5
        close_time_index = 6
        close_time_ms = kline[close_time_index]
        return PricePoint(
            trading_pair=trading_pair,
            price=Decimal(kline[close_price_index]),
            volume=Decimal(kline[volume_index]),
            timestamp=datetime.fromtimestamp(close_time_ms / 1000, tz=UTC),
        )

    @staticmethod
    def _kline_to_candle_row(kline: list[Any]) -> BinanceCandleRow:
        open_time_index = 0
        open_price_index = 1
        high_price_index = 2
        low_price_index = 3
        close_price_index = 4
        volume_index = 5
        open_time_ms = kline[open_time_index]
        # `timeZone=3` выравнивает начало свечи на 00:00 МСК; сама метка
        # времени в ответе всё равно UTC-эпоха — торговый день берём через
        # перевод в Europe/Moscow, а не строковым разбором.
        trading_day = (
            datetime.fromtimestamp(open_time_ms / 1000, tz=UTC)
            .astimezone(MOSCOW_TZ)
            .date()
        )
        return BinanceCandleRow(
            date=trading_day,
            open=Decimal(kline[open_price_index]),
            high=Decimal(kline[high_price_index]),
            low=Decimal(kline[low_price_index]),
            close=Decimal(kline[close_price_index]),
            volume=Decimal(kline[volume_index]),
        )


def next_klines_cursor(last_point: PricePoint) -> datetime:
    """`startTime` следующей страницы `klines` — сразу после последней свечи."""
    return last_point.timestamp + timedelta(milliseconds=1)
