from dmr import (
    Path,
    Query,
    modify,
)

from config.api_base import BaseController
from tickfeeddmr.market_data.api.presenters import crypto as crypto_presenters
from tickfeeddmr.market_data.api.presenters.common import asset_list_out
from tickfeeddmr.market_data.api.schemas.common import (  # noqa: TC001
    AssetOut,
    CursorPage,
    CursorQuery,
)
from tickfeeddmr.market_data.api.schemas.crypto import (  # noqa: TC001
    CryptoCurrentOut,
    CryptoTradeOut,
    SymbolPath,
)
from tickfeeddmr.market_data.services.queries import crypto as crypto_queries
from tickfeeddmr.market_data.services.queries.cursor import decode_cursor

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
