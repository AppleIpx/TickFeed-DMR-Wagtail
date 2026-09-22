from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING

import pytest

from tickfeeddmr.market_data.services.stream_reader import (
    HEARTBEAT,
    Heartbeat,
    LiveStreamSpec,
    read_live_stream,
)
from tickfeeddmr.market_data.services.stream_selection import latest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Collection

    from redis.asyncio import Redis

_ANEXT_TIMEOUT = 5
_Item = tuple[str, int]


def _order_key(item: _Item) -> int:
    return item[1]


def _decode(fields: dict[str, str]) -> _Item:
    """`KeyError`/`ValueError` на битых полях — как `deserialize_trade_event`."""
    return fields["group"], int(fields["seq"])


def _make_spec(
    stream_key: str,
    *,
    wanted: Collection[str] | None = None,
    n: int = 1000,
) -> LiveStreamSpec[_Item, str]:
    accept_raw = (
        (lambda _fields: True)
        if wanted is None
        else (lambda fields, _wanted=frozenset(wanted): fields.get("group") in _wanted)
    )
    return LiveStreamSpec(
        label="test-stream-reader",
        stream_key=stream_key,
        accept_raw=accept_raw,
        decode=_decode,
        group_key=lambda item: item[0],
        order_key=_order_key,
        rule=partial(latest, n=n, key=_order_key),
    )


async def _next_batch(
    agen: AsyncGenerator[list[_Item] | Heartbeat],
) -> list[_Item]:
    """Пропустить heartbeat-и, дождаться первой непустой пачки."""
    while True:
        event = await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        if not isinstance(event, Heartbeat):
            return event


async def test_cursor_starts_at_tail_and_ignores_entries_added_before_start(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    await redis_client.xadd(stream_reader_stream_key, {"group": "a", "seq": "1"})

    spec = _make_spec(stream_reader_stream_key)
    agen = read_live_stream(spec)
    try:
        first_event = await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        assert first_event is HEARTBEAT

        await redis_client.xadd(stream_reader_stream_key, {"group": "a", "seq": "2"})
        batch = await _next_batch(agen)

        assert batch == [("a", 2)]
    finally:
        await agen.aclose()


async def test_accept_raw_filters_out_records_for_unwanted_groups(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    spec = _make_spec(stream_reader_stream_key, wanted={"a"})
    agen = read_live_stream(spec)
    try:
        await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        await redis_client.xadd(stream_reader_stream_key, {"group": "b", "seq": "1"})
        await redis_client.xadd(stream_reader_stream_key, {"group": "a", "seq": "2"})
        batch = await _next_batch(agen)
        assert batch == [("a", 2)]
    finally:
        await agen.aclose()


async def test_malformed_record_is_skipped_without_blocking_rest_of_batch(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = _make_spec(stream_reader_stream_key)
    agen = read_live_stream(spec)
    try:
        await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        await redis_client.xadd(stream_reader_stream_key, {"group": "a"})
        await redis_client.xadd(
            stream_reader_stream_key,
            {"group": "a", "seq": "9"},
        )
        with caplog.at_level(logging.ERROR):
            batch = await _next_batch(agen)
        assert batch == [("a", 9)]
        assert any(
            "Битая запись сделки в стриме" in record.message
            for record in caplog.records
        )
    finally:
        await agen.aclose()


async def test_heartbeat_is_emitted_in_silence_instead_of_empty_batch(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    spec = _make_spec(stream_reader_stream_key)
    agen = read_live_stream(spec)
    try:
        event = await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)

        assert event is HEARTBEAT
    finally:
        await agen.aclose()


async def test_aclose_terminates_generator_without_unhandled_exception(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    """Имитация ухода SSE-клиента: `aclose()` не должен падать/зависать."""
    spec = _make_spec(stream_reader_stream_key)
    agen = read_live_stream(spec)

    await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)

    await asyncio.wait_for(agen.aclose(), timeout=_ANEXT_TIMEOUT)

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
