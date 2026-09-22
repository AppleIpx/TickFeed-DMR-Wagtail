from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import pytest
from django.conf import settings

from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow
from tickfeeddmr.market_data.services.moex_trade_stream import (
    MoexTradeStreamPublisher,
    deserialize_moex_trade,
    serialize_moex_trade,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

_MS_PER_SECOND = 1000
_OLD_ENTRIES_COUNT = 150


def _row(*, trade_id: int = 1) -> MoexTradeRow:
    return MoexTradeRow(
        trade_id=trade_id,
        price=Decimal("312.4"),
        quantity=150,
        side="buy",
        timestamp=datetime(2024, 1, 1, 12, 30, tzinfo=UTC),
        period="N",
    )


def test_round_trip_preserves_trade() -> None:
    row = _row()

    fields = serialize_moex_trade("SBER", row)
    result = deserialize_moex_trade(fields)

    assert result.secid == "SBER"
    assert result.trade == row


def test_serialize_produces_plain_strings_for_xadd() -> None:
    fields = serialize_moex_trade("SBER", _row())

    assert all(isinstance(value, str) for value in fields.values())
    assert fields == {
        "secid": "SBER",
        "trade_id": "1",
        "price": "312.4",
        "quantity": "150",
        "side": "buy",
        "timestamp": "2024-01-01T12:30:00+00:00",
        "period": "N",
    }


@pytest.mark.parametrize(
    "missing_key",
    ["secid", "trade_id", "price", "quantity", "side", "timestamp", "period"],
)
def test_deserialize_raises_key_error_on_missing_field(missing_key: str) -> None:
    fields = serialize_moex_trade("SBER", _row())
    del fields[missing_key]

    with pytest.raises(KeyError):
        deserialize_moex_trade(fields)


def test_deserialize_raises_invalid_operation_on_bad_price() -> None:
    fields = serialize_moex_trade("SBER", _row())
    fields["price"] = "not-a-decimal"

    with pytest.raises(InvalidOperation):
        deserialize_moex_trade(fields)


def test_deserialize_raises_value_error_on_bad_trade_id() -> None:
    fields = serialize_moex_trade("SBER", _row())
    fields["trade_id"] = "not-an-int"

    with pytest.raises(ValueError, match="invalid literal for int"):
        deserialize_moex_trade(fields)


async def test_publish_applies_minid_retention_trimming_old_entries(
    redis_client: Redis,
    moex_trade_stream_key: str,
) -> None:
    now_ms = int(time.time() * _MS_PER_SECOND)
    old_ms = now_ms - 3600 * _MS_PER_SECOND  # час назад -- точно за пределами ретеншна

    for i in range(_OLD_ENTRIES_COUNT):
        await redis_client.xadd(
            moex_trade_stream_key,
            serialize_moex_trade("SBER", _row(trade_id=i)),
            id=f"{old_ms}-{i}",
        )
    before_count = await redis_client.xlen(moex_trade_stream_key)
    assert before_count == _OLD_ENTRIES_COUNT

    publisher = MoexTradeStreamPublisher(
        redis_url=settings.REDIS_URL,
        stream_key=moex_trade_stream_key,
        retention_seconds=1,
    )
    try:
        written = await publisher.publish("SBER", [_row(trade_id=999)])
    finally:
        await publisher.aclose()

    assert written == 1
    after_count = await redis_client.xlen(moex_trade_stream_key)
    assert after_count < before_count / 2

    remaining = await redis_client.xrange(moex_trade_stream_key, min="-", max="+")
    remaining_ids = {entry_id for entry_id, _fields in remaining}
    old_ids = {f"{old_ms}-{i}" for i in range(_OLD_ENTRIES_COUNT)}
    survived_old = remaining_ids & old_ids
    assert len(survived_old) < _OLD_ENTRIES_COUNT / 2


async def test_publish_with_empty_rows_writes_nothing(
    redis_client: Redis,
    moex_trade_stream_key: str,
) -> None:
    publisher = MoexTradeStreamPublisher(
        redis_url=settings.REDIS_URL,
        stream_key=moex_trade_stream_key,
        retention_seconds=300,
    )
    try:
        written = await publisher.publish("SBER", [])
    finally:
        await publisher.aclose()

    assert written == 0
    assert await redis_client.exists(moex_trade_stream_key) == 0
