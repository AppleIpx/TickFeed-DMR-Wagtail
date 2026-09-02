from datetime import datetime
from decimal import Decimal
from typing import Literal, cast

from tickfeeddmr.market_data.providers.base import TradeEvent

MALFORMED_TRADE_EVENT_ERRORS = (KeyError, ValueError, ArithmeticError)


def serialize_trade_event(event: TradeEvent) -> dict[str, str]:
    """`TradeEvent` -> плоский dict строк для `XADD`."""
    return {
        "trading_pair": event.trading_pair,
        "price": str(event.price),
        "volume": str(event.volume),
        "side": event.side,
        "timestamp": event.timestamp.isoformat(),
        "trade_id": event.trade_id,
    }


def deserialize_trade_event(fields: dict[str, str]) -> TradeEvent:
    """Обратное преобразование к `serialize_trade_event`.

    Бросает один из `MALFORMED_TRADE_EVENT_ERRORS` (`KeyError`/`ValueError`/
    `decimal.InvalidOperation`) на отсутствующих или битых полях —
    вызывающий код (management-команда консьюмера) сам решает, что делать с
    "отравленным" сообщением.
    """
    return TradeEvent(
        trading_pair=fields["trading_pair"],
        price=Decimal(fields["price"]),
        volume=Decimal(fields["volume"]),
        side=cast("Literal['buy', 'sell']", fields["side"]),
        timestamp=datetime.fromisoformat(fields["timestamp"]),
        trade_id=fields["trade_id"],
    )
