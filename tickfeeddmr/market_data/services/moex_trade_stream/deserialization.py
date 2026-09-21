from datetime import datetime
from decimal import Decimal
from typing import Literal, cast

from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow
from tickfeeddmr.market_data.services.moex_trade_stream.schemas import MoexStreamTrade


def deserialize_moex_trade(fields: dict[str, str]) -> MoexStreamTrade:
    """Обратное преобразование к `serialize_moex_trade`.

    Бросает один из `MALFORMED_TRADE_EVENT_ERRORS` (`trade_stream.py`) на
    отсутствующих или битых полях — вызывающий код решает, что делать с
    «отравленной» записью.
    """
    return MoexStreamTrade(
        secid=fields["secid"],
        trade=MoexTradeRow(
            trade_id=int(fields["trade_id"]),
            price=Decimal(fields["price"]),
            quantity=int(fields["quantity"]),
            side=cast("Literal['buy', 'sell']", fields["side"]),
            timestamp=datetime.fromisoformat(fields["timestamp"]),
            period=fields["period"],
        ),
    )
