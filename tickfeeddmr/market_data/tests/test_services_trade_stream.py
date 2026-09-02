"""Юнит-тесты `serialize_trade_event`/`deserialize_trade_event`.

Round-trip и отдельные кейсы с битыми полями.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import pytest

from tickfeeddmr.market_data.providers.base import TradeEvent
from tickfeeddmr.market_data.services.trade_stream import (
    deserialize_trade_event,
    serialize_trade_event,
)


def _event() -> TradeEvent:
    return TradeEvent(
        trading_pair="BTCUSDT",
        price=Decimal("50000.12345678"),
        volume=Decimal("0.5"),
        side="sell",
        timestamp=datetime(2024, 1, 1, 12, 30, tzinfo=UTC),
        trade_id="12345",
    )


def test_round_trip_preserves_event() -> None:
    event = _event()

    assert deserialize_trade_event(serialize_trade_event(event)) == event


def test_serialize_produces_plain_strings_for_xadd() -> None:
    fields = serialize_trade_event(_event())

    assert all(isinstance(value, str) for value in fields.values())
    assert fields == {
        "trading_pair": "BTCUSDT",
        "price": "50000.12345678",
        "volume": "0.5",
        "side": "sell",
        "timestamp": "2024-01-01T12:30:00+00:00",
        "trade_id": "12345",
    }


@pytest.mark.parametrize(
    "missing_key",
    ["trading_pair", "price", "volume", "side", "timestamp", "trade_id"],
)
def test_deserialize_raises_key_error_on_missing_field(missing_key: str) -> None:
    fields = serialize_trade_event(_event())
    del fields[missing_key]

    with pytest.raises(KeyError):
        deserialize_trade_event(fields)


def test_deserialize_raises_invalid_operation_on_bad_price() -> None:
    fields = serialize_trade_event(_event())
    fields["price"] = "not-a-decimal"

    with pytest.raises(InvalidOperation):
        deserialize_trade_event(fields)


def test_deserialize_raises_invalid_operation_on_bad_volume() -> None:
    fields = serialize_trade_event(_event())
    fields["volume"] = "not-a-decimal"

    with pytest.raises(InvalidOperation):
        deserialize_trade_event(fields)


def test_deserialize_raises_value_error_on_bad_timestamp() -> None:
    fields = serialize_trade_event(_event())
    fields["timestamp"] = "not-a-timestamp"

    with pytest.raises(ValueError, match="Invalid isoformat string"):
        deserialize_trade_event(fields)
