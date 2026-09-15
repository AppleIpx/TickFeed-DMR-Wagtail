from typing import TYPE_CHECKING

from tickfeeddmr.market_data.models import CryptoAsset, CryptoPriceSnapshot
from tickfeeddmr.market_data.services.queries.cursor import fetch_cursor_page
from tickfeeddmr.market_data.services.queries.errors import (
    AssetNotFoundError,
    NoDataYetError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.services.queries.types import Cursor


async def list_assets() -> Sequence[CryptoAsset]:
    """Активные крипто-пары."""
    return [asset async for asset in CryptoAsset.objects.filter(is_active=True)]


async def get_current(symbol: str) -> tuple[CryptoAsset, CryptoPriceSnapshot]:
    """Актив и его последний снапшот цены.

    `AssetNotFoundError` — актива с таким `symbol` нет либо он неактивен.
    `NoDataYetError` — актив есть, но ни одного снапшота ещё не записано
    (например, только что добавлен в админке, стрим ещё не догнал).
    """
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    snapshot = await asset.price_snapshots.afirst()
    if snapshot is None:
        msg = f"По активу {symbol!r} ещё нет данных"
        raise NoDataYetError(msg)

    return asset, snapshot


async def list_trades(
    symbol: str,
    *,
    cursor: Cursor | None,
    limit: int,
) -> tuple[list[CryptoPriceSnapshot], str | None]:
    """Лента сделок по активу — только строки с известными `trade_id`/`side`."""
    asset = await CryptoAsset.objects.filter(symbol=symbol, is_active=True).afirst()
    if asset is None:
        msg = f"Крипто-актив {symbol!r} не найден"
        raise AssetNotFoundError(msg)

    queryset = CryptoPriceSnapshot.objects.filter(
        asset=asset,
        trade_id__isnull=False,
        side__isnull=False,
    )
    return await fetch_cursor_page(queryset, cursor=cursor, limit=limit)
