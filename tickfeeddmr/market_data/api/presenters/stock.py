from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Literal, cast

from django.conf import settings

from tickfeeddmr.market_data.api.presenters.common import (
    asset_out,
    freshness,
    intraday_out,
    trades_page_out,
)
from tickfeeddmr.market_data.api.presenters.stream import sse_events, stream_warning
from tickfeeddmr.market_data.api.schemas.stock import (
    StockAssetOut,
    StockCurrentOut,
    StockPricePointOut,
    StockTradeEventOut,
    StockTradeOut,
)
from tickfeeddmr.market_data.providers.moex.types import MOEX_DATA_DELAY_SECONDS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Sequence
    from datetime import date
    from decimal import Decimal

    from dmr.streaming.sse import SSEvent

    from tickfeeddmr.market_data.api.schemas.common import CursorPage, IntradayOut
    from tickfeeddmr.market_data.api.schemas.stock import StockStreamEventOut
    from tickfeeddmr.market_data.models import (
        StockAsset,
        StockDailyCandle,
        StockPriceSnapshot,
        StockTrade,
    )
    from tickfeeddmr.market_data.services.moex_trade_stream import MoexStreamTrade
    from tickfeeddmr.market_data.services.queries.types import (
        IntradayPoint,
        StreamTargets,
    )
    from tickfeeddmr.market_data.services.stream_reader import Heartbeat

MOSCOW_TZ = settings.MOSCOW_TZ


def _day_start_utc(day: date) -> datetime:
    """Начало торгового дня (00:00 МСК) в UTC — `StockPricePointOut.timestamp`."""
    return datetime.combine(day, time.min, tzinfo=MOSCOW_TZ).astimezone(UTC)


def _optional_decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def asset_list_out(assets: Sequence[StockAsset]) -> list[StockAssetOut]:
    """Список акций с флагом ленты сделок.

    Фронт решает по нему, звать ли `/trades`/подписываться в SSE.
    """
    return [
        StockAssetOut(
            symbol=asset.symbol,
            display_name=asset.display_name,
            is_active=asset.is_active,
            track_trades=asset.track_trades,
        )
        for asset in assets
    ]


def current_out(asset: StockAsset, snapshot: StockPriceSnapshot) -> StockCurrentOut:
    return StockCurrentOut(
        asset=asset_out(asset),
        last=_optional_decimal_str(snapshot.last),
        open=_optional_decimal_str(snapshot.open),
        high=_optional_decimal_str(snapshot.high),
        low=_optional_decimal_str(snapshot.low),
        change=_optional_decimal_str(snapshot.change),
        change_percent=_optional_decimal_str(snapshot.change_percent),
        volume=snapshot.volume,
        num_trades=snapshot.num_trades,
        freshness=freshness(
            timestamp=snapshot.timestamp,
            data_delay_seconds=MOEX_DATA_DELAY_SECONDS,
        ),
    )


def trade_out(row: StockTrade) -> StockTradeOut:
    return StockTradeOut(
        timestamp=row.timestamp,
        price=str(row.price),
        quantity=row.quantity,
        side=cast('Literal["buy", "sell"]', row.side),
        trade_id=row.trade_id,
        period=row.period,
    )


def trades_page(
    items: list[StockTradeOut],
    next_cursor: str | None,
) -> CursorPage[StockTradeOut]:
    return trades_page_out(
        items,
        next_cursor,
        data_delay_seconds=MOEX_DATA_DELAY_SECONDS,
    )


def intraday(points: Sequence[IntradayPoint]) -> IntradayOut:
    return intraday_out(points, data_delay_seconds=MOEX_DATA_DELAY_SECONDS)


def history_point_out(candle: StockDailyCandle) -> StockPricePointOut:
    return StockPricePointOut(
        timestamp=_day_start_utc(candle.date),
        open=str(candle.open),
        high=str(candle.high),
        low=str(candle.low),
        close=str(candle.close),
        volume=candle.volume,
    )


def history_out(candles: Sequence[StockDailyCandle]) -> list[StockPricePointOut]:
    return [history_point_out(candle) for candle in candles]


def stream_events(
    targets: StreamTargets,
    batches: AsyncGenerator[list[MoexStreamTrade] | Heartbeat],
) -> AsyncIterator[SSEvent[StockStreamEventOut]]:
    """SSE-события потока акций: `warning` -> `trade` -> `heartbeat`."""

    def to_trade_event(item: MoexStreamTrade) -> StockTradeEventOut:
        trade = item.trade
        return StockTradeEventOut(
            secid=item.secid,
            timestamp=trade.timestamp,
            price=str(trade.price),
            quantity=trade.quantity,
            side=trade.side,
            trade_id=trade.trade_id,
            period=trade.period,
            data_delay_seconds=MOEX_DATA_DELAY_SECONDS,
        )

    return sse_events(
        batches,
        to_trade_event=to_trade_event,
        warning=stream_warning(
            targets,
            list_url="/api/stocks/",
            reason="Тикеры не найдены, отключены или без ленты сделок",
        ),
    )
