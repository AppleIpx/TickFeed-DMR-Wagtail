from collections.abc import AsyncIterator  # noqa: TC003
from http import HTTPStatus

from dmr import (
    Path,
    Query,
    ResponseSpec,
    modify,
)
from dmr.errors import ErrorModel
from dmr.streaming.sse import SSEvent  # noqa: TC002

from config.api_base import BaseController, BaseSSEController
from tickfeeddmr.market_data.api.presenters import crypto as crypto_presenters
from tickfeeddmr.market_data.api.presenters.common import asset_list_out
from tickfeeddmr.market_data.api.schemas.common import (  # noqa: TC001
    AssetOut,
    CursorPage,
    CursorQuery,
    HistoryQuery,
    IntradayOut,
    PricePointOut,
)
from tickfeeddmr.market_data.api.schemas.crypto import (  # noqa: TC001
    CryptoCurrentOut,
    CryptoStreamEventOut,
    CryptoTradeOut,
    SymbolPath,
    SymbolsQuery,
)
from tickfeeddmr.market_data.services.live_trades import crypto_trade_stream
from tickfeeddmr.market_data.services.queries import crypto as crypto_queries
from tickfeeddmr.market_data.services.queries.cursor import decode_cursor
from tickfeeddmr.market_data.services.queries.tickers import parse_tickers

_TAGS = ["Крипта"]


class CryptoAssetListController(BaseController):
    """`GET /api/crypto/assets/` — активные крипто-пары."""

    @modify(tags=_TAGS)
    async def get(self) -> list[AssetOut]:
        assets = await crypto_queries.list_assets()
        return asset_list_out(assets)


class CryptoAssetCurrentController(BaseController):
    """`GET /api/crypto/assets/{symbol}/current` — текущая цена."""

    @modify(tags=_TAGS)
    async def get(self, parsed_path: Path[SymbolPath]) -> CryptoCurrentOut:
        asset, snapshot = await crypto_queries.get_current(parsed_path.symbol)
        return crypto_presenters.current_out(asset, snapshot)


class CryptoTradesController(BaseController):
    """`GET /api/crypto/assets/{symbol}/trades` — лента сделок, курсорная пагинация."""

    @modify(tags=_TAGS)
    async def get(
        self,
        parsed_path: Path[SymbolPath],
        parsed_query: Query[CursorQuery],
    ) -> CursorPage[CryptoTradeOut]:
        cursor = decode_cursor(parsed_query.cursor) if parsed_query.cursor else None
        rows, next_cursor = await crypto_queries.list_trades(
            parsed_path.symbol,
            cursor=cursor,
            limit=parsed_query.limit,
        )
        items = [crypto_presenters.trade_out(row) for row in rows]
        return crypto_presenters.trades_page(items, next_cursor)


class CryptoIntradayController(BaseController):
    """`GET /api/crypto/assets/{symbol}/intraday` — скользящие последние 24 часа."""

    @modify(tags=_TAGS)
    async def get(self, parsed_path: Path[SymbolPath]) -> IntradayOut:
        points = await crypto_queries.get_intraday(parsed_path.symbol)
        return crypto_presenters.intraday(points)


class CryptoHistoryController(BaseController):
    """`GET /api/crypto/assets/{symbol}/history` — дневные свечи за период."""

    @modify(tags=_TAGS)
    async def get(
        self,
        parsed_path: Path[SymbolPath],
        parsed_query: Query[HistoryQuery],
    ) -> list[PricePointOut]:
        candles = await crypto_queries.get_history(
            parsed_path.symbol,
            date_from=parsed_query.date_from,
            date_to=parsed_query.date_to,
        )
        return crypto_presenters.history_out(candles)


class CryptoStreamController(BaseSSEController):
    """`GET /api/crypto/stream` — SSE-поток сделок крипты.

    Без параметров — все активные пары, `?symbols=BTC,ETH` — только
    указанные. Ни один тикер не найден — 404 (а не 200 + закрытый поток:
    `EventSource` на 404 перестаёт переподключаться).
    """

    @modify(
        tags=_TAGS,
        extra_responses=[
            ResponseSpec(ErrorModel, status_code=HTTPStatus.NOT_FOUND),
        ],
    )
    async def get(
        self,
        parsed_query: Query[SymbolsQuery],
    ) -> AsyncIterator[SSEvent[CryptoStreamEventOut]]:
        targets = await crypto_queries.resolve_stream_targets(
            parse_tickers(parsed_query.symbols),
        )
        await self.release_db_connections()
        return crypto_presenters.stream_events(
            targets,
            crypto_trade_stream(targets.symbols_by_stream_key),
        )
