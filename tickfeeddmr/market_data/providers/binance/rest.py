import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx

from tickfeeddmr.market_data.providers.base import PricePoint
from tickfeeddmr.market_data.providers.exceptions import ProviderResponseError

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

KLINES_PATH = "/api/v3/klines"
TICKER_PRICE_PATH = "/api/v3/ticker/price"
MAX_KLINES_LIMIT = 1000
REQUEST_TIMEOUT_SECONDS = 10.0


class BinanceRestClient:
    """Клиент к двум REST-эндпоинтам Binance: `klines` и `ticker/price`.

    Нормализации ответа в `PricePoint` —
    пагинация истории и выбор эндпоинта остаются на стороне
    `BinanceProvider`.
    """

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_current_price(self, trading_pair: str) -> PricePoint:
        response = await self._client.get(
            TICKER_PRICE_PATH,
            params={"symbol": trading_pair},
        )
        self._raise_for_status(response)
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

        response = await self._client.get(KLINES_PATH, params=params)
        self._raise_for_status(response)
        return [
            self._kline_to_price_point(trading_pair, kline) for kline in response.json()
        ]

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
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_error:
            logger.error(
                "Binance REST error %s: %s",
                response.status_code,
                response.text,
            )
            msg = f"Binance REST request failed with status {response.status_code}"
            raise ProviderResponseError(msg)


def next_klines_cursor(last_point: PricePoint) -> datetime:
    """`startTime` следующей страницы `klines` — сразу после последней свечи."""
    return last_point.timestamp + timedelta(milliseconds=1)
