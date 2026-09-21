from typing import TYPE_CHECKING

import msgspec

from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow

if TYPE_CHECKING:
    from datetime import datetime


class MoexStreamTrade(msgspec.Struct, frozen=True):
    """Сделка из стрима акций: бумага + строка ленты ISS."""

    secid: str
    trade: MoexTradeRow


def trade_recency(row: MoexTradeRow) -> tuple[datetime, int]:
    """Ключ «свежести» сделки для правил отбора.

    `SYSTIME` у ISS с точностью до секунды, а сделок в секунду может быть
    несколько — `TRADENO` (монотонно растёт) разводит их детерминированно.
    """
    return row.timestamp, row.trade_id
