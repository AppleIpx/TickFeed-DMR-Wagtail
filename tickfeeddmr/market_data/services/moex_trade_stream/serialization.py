from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow


def serialize_moex_trade(secid: str, row: MoexTradeRow) -> dict[str, str]:
    """Сделка MOEX -> плоский dict строк для `XADD`."""
    return {
        "secid": secid,
        "trade_id": str(row.trade_id),
        "price": str(row.price),
        "quantity": str(row.quantity),
        "side": row.side,
        "timestamp": row.timestamp.isoformat(),
        "period": row.period,
    }
