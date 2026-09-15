from typing import TYPE_CHECKING

from tickfeeddmr.market_data.models import StockAsset, StockPriceSnapshot, StockTrade
from tickfeeddmr.market_data.services.queries.cursor import fetch_cursor_page
from tickfeeddmr.market_data.services.queries.errors import (
    AssetNotFoundError,
    NoDataYetError,
    TradesNotTrackedError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.services.queries.types import Cursor


async def list_assets() -> Sequence[StockAsset]:
    """Активные акции."""
    return [asset async for asset in StockAsset.objects.filter(is_active=True)]


async def get_current(secid: str) -> tuple[StockAsset, StockPriceSnapshot]:
    """Актив и его последний снимок борда.

    `AssetNotFoundError` — бумаги с таким `secid` нет либо она неактивна.
    `NoDataYetError` — бумага есть, но ни одного снимка ещё не записано.
    """
    asset = await StockAsset.objects.filter(symbol=secid, is_active=True).afirst()
    if asset is None:
        msg = f"Акция {secid!r} не найдена"
        raise AssetNotFoundError(msg)

    snapshot = await asset.price_snapshots.afirst()
    if snapshot is None:
        msg = f"По бумаге {secid!r} ещё нет данных"
        raise NoDataYetError(msg)

    return asset, snapshot


async def list_trades(
    secid: str,
    *,
    cursor: Cursor | None,
    limit: int,
) -> tuple[list[StockTrade], str | None]:
    """Лента сделок по бумаге — только для активов с `track_trades=True`.

    Не фильтрует по `StockTrade.period` (аукционные сделки) — решение
    этапа 8a: ISS не документирует полный список кодов, фильтрация по
    недокументированному значению рискует молча выкидывать легитимные
    сделки. Ручка отдаёт всё как есть, `period` уходит в схему
    (`StockTradeOut.period`) как есть — фильтрация, если понадобится,
    остаётся на фронте.
    """
    asset = await StockAsset.objects.filter(symbol=secid, is_active=True).afirst()
    if asset is None:
        msg = f"Акция {secid!r} не найдена"
        raise AssetNotFoundError(msg)
    if not asset.track_trades:
        msg = f"Лента сделок для {secid!r} не ведётся"
        raise TradesNotTrackedError(msg)

    queryset = StockTrade.objects.filter(asset=asset)
    return await fetch_cursor_page(queryset, cursor=cursor, limit=limit)
