from dmr import (
    Path,
    Query,
    modify,
)

from config.api_base import BaseController
from tickfeeddmr.market_data.api.presenters import stock as stock_presenters
from tickfeeddmr.market_data.api.presenters.common import asset_list_out
from tickfeeddmr.market_data.api.schemas.common import (  # noqa: TC001
    AssetOut,
    CursorPage,
    CursorQuery,
    HistoryQuery,
    IntradayOut,
)
from tickfeeddmr.market_data.api.schemas.stock import (  # noqa: TC001
    SecidPath,
    StockCurrentOut,
    StockPricePointOut,
    StockTradeOut,
)
from tickfeeddmr.market_data.services.queries import stock as stock_queries
from tickfeeddmr.market_data.services.queries.cursor import decode_cursor

_TAGS = ["Акции"]


class StockAssetListController(BaseController):
    """`GET /api/stocks/` — активные акции."""

    @modify(tags=_TAGS)
    async def get(self) -> list[AssetOut]:
        assets = await stock_queries.list_assets()
        return asset_list_out(assets)


class StockAssetCurrentController(BaseController):
    """`GET /api/stocks/{secid}/current` — текущий снимок борда."""

    @modify(tags=_TAGS)
    async def get(self, parsed_path: Path[SecidPath]) -> StockCurrentOut:
        asset, snapshot = await stock_queries.get_current(parsed_path.secid)
        return stock_presenters.current_out(asset, snapshot)


class StockTradesController(BaseController):
    """`GET /api/stocks/{secid}/trades` — лента сделок, курсорная пагинация."""

    @modify(tags=_TAGS)
    async def get(
        self,
        parsed_path: Path[SecidPath],
        parsed_query: Query[CursorQuery],
    ) -> CursorPage[StockTradeOut]:
        cursor = decode_cursor(parsed_query.cursor) if parsed_query.cursor else None
        rows, next_cursor = await stock_queries.list_trades(
            parsed_path.secid,
            cursor=cursor,
            limit=parsed_query.limit,
        )
        items = [stock_presenters.trade_out(row) for row in rows]
        return stock_presenters.trades_page(items, next_cursor)


class StockIntradayController(BaseController):
    """`GET /api/stocks/{secid}/intraday` — скользящие последние 24 часа."""

    @modify(tags=_TAGS)
    async def get(self, parsed_path: Path[SecidPath]) -> IntradayOut:
        points = await stock_queries.get_intraday(parsed_path.secid)
        return stock_presenters.intraday(points)


class StockHistoryController(BaseController):
    """`GET /api/stocks/{secid}/history` — дневные свечи за период."""

    @modify(tags=_TAGS)
    async def get(
        self,
        parsed_path: Path[SecidPath],
        parsed_query: Query[HistoryQuery],
    ) -> list[StockPricePointOut]:
        candles = await stock_queries.get_history(
            parsed_path.secid,
            date_from=parsed_query.date_from,
            date_to=parsed_query.date_to,
        )
        return stock_presenters.history_out(candles)
