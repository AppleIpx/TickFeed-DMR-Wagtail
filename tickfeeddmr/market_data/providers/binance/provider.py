from typing import TYPE_CHECKING

from tickfeeddmr.market_data.providers.base import (
    AssetDataProvider,
    PricePoint,
    TradeEvent,
)
from tickfeeddmr.market_data.providers.binance.rest import (
    MAX_KLINES_LIMIT,
    BinanceRestClient,
    next_klines_cursor,
)
from tickfeeddmr.market_data.providers.binance.websocket import (
    BinanceTradeStreamConsumer,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection, Sequence
    from datetime import datetime

EXCHANGE = "BINANCE"


class BinanceProvider(AssetDataProvider):
    """Реализация `AssetDataProvider` поверх REST и WS Binance."""

    def __init__(
        self,
        *,
        rest_base_url: str,
        ws_base_url: str,
        rest_client: BinanceRestClient | None = None,
    ) -> None:
        self._ws_base_url = ws_base_url
        self._rest = rest_client or BinanceRestClient(base_url=rest_base_url)

    async def aclose(self) -> None:
        await self._rest.aclose()

    async def fetch_current(self, trading_pair: str) -> PricePoint:
        return await self._rest.get_current_price(trading_pair)

    async def fetch_history(
        self,
        trading_pair: str,
        *,
        start: datetime,
        end: datetime | None = None,
        interval: str = "1m",
    ) -> AsyncIterator[PricePoint]:
        cursor = start
        while True:
            batch = await self._rest.get_klines(
                trading_pair,
                interval=interval,
                start_time=cursor,
                end_time=end,
            )
            if not batch:
                return
            for point in batch:
                yield point

            if len(batch) < MAX_KLINES_LIMIT:
                return
            cursor = next_klines_cursor(batch[-1])
            if end is not None and cursor >= end:
                return

    def trade_stream(
        self,
        trading_pairs: Collection[str] = (),
    ) -> BinanceTradeStreamConsumer:
        """Управляемый хэндл стрима: набор пар меняется на лету через
        `update_pairs`, без переподключения. `stream()` ниже — то же самое
        со статичным набором, для соответствия `AssetDataProvider`.
        """
        return BinanceTradeStreamConsumer(
            ws_base_url=self._ws_base_url,
            trading_pairs=trading_pairs,
        )

    def stream(self, trading_pairs: Sequence[str]) -> AsyncIterator[TradeEvent]:
        return self.trade_stream(trading_pairs).stream()
