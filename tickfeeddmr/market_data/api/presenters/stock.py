from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Literal, cast

from django.conf import settings

from tickfeeddmr.market_data.api.presenters.common import (
    asset_out,
    freshness,
    intraday_out,
    trades_page_out,
)
from tickfeeddmr.market_data.api.schemas.stock import (
    MOEX_DATA_DELAY_SECONDS,
    StockCurrentOut,
    StockPricePointOut,
    StockTradeOut,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date
    from decimal import Decimal

    from tickfeeddmr.market_data.api.schemas.common import CursorPage, IntradayOut
    from tickfeeddmr.market_data.models import (
        StockAsset,
        StockDailyCandle,
        StockPriceSnapshot,
        StockTrade,
    )
    from tickfeeddmr.market_data.services.queries.types import IntradayPoint

MOSCOW_TZ = settings.MOSCOW_TZ


def _day_start_utc(day: date) -> datetime:
    """Начало торгового дня (00:00 МСК) в UTC — `StockPricePointOut.timestamp`."""
    return datetime.combine(day, time.min, tzinfo=MOSCOW_TZ).astimezone(UTC)


def _optional_decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


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
