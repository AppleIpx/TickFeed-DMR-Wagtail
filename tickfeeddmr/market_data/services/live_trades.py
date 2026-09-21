from functools import partial
from operator import attrgetter
from typing import TYPE_CHECKING

from django.conf import settings

from tickfeeddmr.market_data.services.moex_trade_stream import (
    deserialize_moex_trade,
    trade_recency,
)
from tickfeeddmr.market_data.services.stream_reader import (
    LiveStreamSpec,
    read_live_stream,
)
from tickfeeddmr.market_data.services.stream_selection import latest
from tickfeeddmr.market_data.services.stream_settings import validate_sse_settings
from tickfeeddmr.market_data.services.trade_stream import deserialize_trade_event

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Collection

    from tickfeeddmr.market_data.providers.base import TradeEvent
    from tickfeeddmr.market_data.services.moex_trade_stream import MoexStreamTrade
    from tickfeeddmr.market_data.services.stream_reader import Heartbeat


validate_sse_settings()


def crypto_trade_stream(
    trading_pairs: Collection[str],
) -> AsyncGenerator[list[TradeEvent] | Heartbeat]:
    """Сделки Binance по `trading_pairs`: последние N на пару за окно."""
    wanted = frozenset(trading_pairs)
    order_key = attrgetter("timestamp")
    spec: LiveStreamSpec[TradeEvent, str] = LiveStreamSpec(
        label="SSE-стрим крипто-сделок",
        stream_key=settings.MARKET_DATA_TRADE_STREAM_KEY,
        accept_raw=lambda fields: fields.get("trading_pair") in wanted,
        decode=deserialize_trade_event,
        group_key=attrgetter("trading_pair"),
        order_key=order_key,
        rule=partial(latest, n=settings.MARKET_DATA_SSE_TOP_N, key=order_key),
    )
    return read_live_stream(spec)


def stock_trade_stream(
    secids: Collection[str],
) -> AsyncGenerator[list[MoexStreamTrade] | Heartbeat]:
    """Сделки акций MOEX по `secids`: последние N на бумагу за окно."""
    wanted = frozenset(secids)

    def order_key(item: MoexStreamTrade) -> tuple[object, int]:
        return trade_recency(item.trade)

    spec: LiveStreamSpec[MoexStreamTrade, str] = LiveStreamSpec(
        label="SSE-стрим сделок акций",
        stream_key=settings.MOEX_TRADE_STREAM_KEY,
        accept_raw=lambda fields: fields.get("secid") in wanted,
        decode=deserialize_moex_trade,
        group_key=attrgetter("secid"),
        order_key=order_key,
        rule=partial(latest, n=settings.MARKET_DATA_SSE_TOP_N, key=order_key),
    )
    return read_live_stream(spec)
