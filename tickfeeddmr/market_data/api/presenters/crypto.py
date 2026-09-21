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
from tickfeeddmr.market_data.api.schemas.common import PricePointOut
from tickfeeddmr.market_data.api.schemas.crypto import (
    BINANCE_DATA_DELAY_SECONDS,
    CryptoCurrentOut,
    CryptoTradeEventOut,
    CryptoTradeOut,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Sequence
    from datetime import date

    from dmr.streaming.sse import SSEvent

    from tickfeeddmr.market_data.api.schemas.common import CursorPage, IntradayOut
    from tickfeeddmr.market_data.api.schemas.crypto import CryptoStreamEventOut
    from tickfeeddmr.market_data.models import (
        CryptoAsset,
        CryptoDailyCandle,
        CryptoPriceSnapshot,
    )
    from tickfeeddmr.market_data.providers.base import TradeEvent
    from tickfeeddmr.market_data.services.queries.types import (
        IntradayPoint,
        StreamTargets,
    )
    from tickfeeddmr.market_data.services.stream_reader import Heartbeat

MOSCOW_TZ = settings.MOSCOW_TZ


def _day_start_utc(day: date) -> datetime:
    """Начало торгового дня (00:00 МСК) в UTC — `PricePointOut.timestamp`.

    Свеча несёт только `date` (без времени), а поле унаследовано от
    `PricePointBase.timestamp: datetime` — тем же способом домен уже
    приводит календарную дату ко времени, что и `cbr_polling/rates.py`
    для `FiatPriceSnapshot.timestamp`.
    """
    return datetime.combine(day, time.min, tzinfo=MOSCOW_TZ).astimezone(UTC)


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


def intraday(points: Sequence[IntradayPoint]) -> IntradayOut:
    return intraday_out(points, data_delay_seconds=BINANCE_DATA_DELAY_SECONDS)


def history_point_out(candle: CryptoDailyCandle) -> PricePointOut:
    return PricePointOut(
        timestamp=_day_start_utc(candle.date),
        open=str(candle.open),
        high=str(candle.high),
        low=str(candle.low),
        close=str(candle.close),
        volume=str(candle.volume),
    )


def history_out(candles: Sequence[CryptoDailyCandle]) -> list[PricePointOut]:
    return [history_point_out(candle) for candle in candles]


def stream_events(
    targets: StreamTargets,
    batches: AsyncGenerator[list[TradeEvent] | Heartbeat],
) -> AsyncIterator[SSEvent[CryptoStreamEventOut]]:
    """SSE-события потока крипты: `warning` -> `trade` -> `heartbeat`."""
    symbols = targets.symbols_by_stream_key

    def to_trade_event(event: TradeEvent) -> CryptoTradeEventOut:
        return CryptoTradeEventOut(
            symbol=symbols[event.trading_pair],
            timestamp=event.timestamp,
            price=str(event.price),
            volume=str(event.volume),
            side=event.side,
            trade_id=event.trade_id,
            data_delay_seconds=BINANCE_DATA_DELAY_SECONDS,
        )

    return sse_events(
        batches,
        to_trade_event=to_trade_event,
        warning=stream_warning(
            targets,
            list_url="/api/crypto/assets/",
            reason="Тикеры не найдены или отключены",
        ),
    )
