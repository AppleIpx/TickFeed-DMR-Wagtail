from typing import TYPE_CHECKING, Literal, cast

from tickfeeddmr.market_data.api.presenters.common import (
    asset_out,
    freshness,
    trades_page_out,
)
from tickfeeddmr.market_data.api.schemas.crypto import (
    BINANCE_DATA_DELAY_SECONDS,
    CryptoCurrentOut,
    CryptoTradeOut,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.api.schemas.common import CursorPage
    from tickfeeddmr.market_data.models import CryptoAsset, CryptoPriceSnapshot


def current_out(asset: CryptoAsset, snapshot: CryptoPriceSnapshot) -> CryptoCurrentOut:
    return CryptoCurrentOut(
        asset=asset_out(asset),
        price=str(snapshot.price),
        volume=str(snapshot.volume) if snapshot.volume is not None else None,
        freshness=freshness(
            timestamp=snapshot.timestamp,
            data_delay_seconds=BINANCE_DATA_DELAY_SECONDS,
        ),
    )


def trade_out(row: CryptoPriceSnapshot) -> CryptoTradeOut:
    return CryptoTradeOut(
        timestamp=row.timestamp,
        price=str(row.price),
        volume=str(row.volume),
        side=cast('Literal["buy", "sell"]', row.side),
        trade_id=cast("str", row.trade_id),
    )


def trades_page(
    items: list[CryptoTradeOut],
    next_cursor: str | None,
) -> CursorPage[CryptoTradeOut]:
    return trades_page_out(
        items,
        next_cursor,
        data_delay_seconds=BINANCE_DATA_DELAY_SECONDS,
    )
