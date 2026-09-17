from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tickfeeddmr.market_data.api.schemas.common import (
    AssetOut,
    CursorPage,
    DataFreshness,
    IntradayOut,
    LinearPricePointOut,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.models import AssetBase
    from tickfeeddmr.market_data.services.queries.types import IntradayPoint


def asset_out(asset: AssetBase) -> AssetOut:
    return AssetOut(
        symbol=asset.symbol,
        display_name=asset.display_name,
        is_active=asset.is_active,
    )


def asset_list_out(assets: Sequence[AssetBase]) -> list[AssetOut]:
    """Список активов для ручек вида `GET /api/<domain>/assets/`."""
    return [asset_out(asset) for asset in assets]


def freshness(*, timestamp: datetime, data_delay_seconds: int) -> DataFreshness:
    """Собрать `DataFreshness` — `is_realtime` всегда выводится из задержки."""
    return DataFreshness(
        timestamp=timestamp,
        data_delay_seconds=data_delay_seconds,
        is_realtime=data_delay_seconds == 0,
    )


def trades_page_out[T](
    items: list[T],
    next_cursor: str | None,
    *,
    data_delay_seconds: int,
) -> CursorPage[T]:
    """Собрать страницу ленты сделок — тело одинаково для всех доменов."""
    return CursorPage(
        items=items,
        next_cursor=next_cursor,
        freshness=freshness(
            timestamp=datetime.now(UTC),
            data_delay_seconds=data_delay_seconds,
        ),
    )


def intraday_out(
    points: Sequence[IntradayPoint],
    *,
    data_delay_seconds: int,
) -> IntradayOut:
    """Собрать ответ `intraday` — одна свежесть на весь ответ, не на точку.

    Тело одинаково для крипты и акций (общая `IntradayPoint`/
    `LinearPricePointOut`) — домен-специфичен только источник точек
    (`services/queries/{crypto,stock}.py::get_intraday`).
    """
    items = [
        LinearPricePointOut(
            timestamp=point.timestamp,
            price=str(point.price),
            volume=str(point.volume),
        )
        for point in points
    ]
    latest = max((point.timestamp for point in points), default=None)
    return IntradayOut(
        points=items,
        freshness=freshness(
            timestamp=latest or datetime.now(UTC),
            data_delay_seconds=data_delay_seconds,
        ),
    )
