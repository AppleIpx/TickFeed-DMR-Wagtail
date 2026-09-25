from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from functools import partial
from typing import TYPE_CHECKING

import pytest

from tickfeeddmr.market_data.services.stream_reader import (
    HEARTBEAT,
    Heartbeat,
    LiveStreamSpec,
    subscribe,
)
from tickfeeddmr.market_data.services.stream_reader import hub as hub_module
from tickfeeddmr.market_data.services.stream_selection import latest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from pytest_django.fixtures import Settings
    from redis.asyncio import Redis

_ANEXT_TIMEOUT = 5
_Item = tuple[str, int]


def _order_key(item: _Item) -> int:
    return item[1]


def _decode(fields: dict[str, str]) -> _Item:
    """`KeyError`/`ValueError` на битых полях — как `deserialize_trade_event`."""
    return fields["group"], int(fields["seq"])


def _make_spec(stream_key: str, *, n: int = 1000) -> LiveStreamSpec[_Item, str]:
    return LiveStreamSpec(
        label="test-stream-reader",
        stream_key=stream_key,
        raw_group_key=lambda fields: fields.get("group"),
        decode=_decode,
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


async def _wait_until_closed(agen: AsyncGenerator[list[_Item] | Heartbeat]) -> None:
    """Дождаться `StopAsyncIteration`, допуская сколько угодно heartbeat-ов до неё.

    Закрытие подписчик обнаруживает только проснувшись от своего `wait()`
    , так что между нештатной остановкой хаба и
    закрытием генератора может уложиться ещё один heartbeat-цикл.
    """

    async def _drain() -> None:
        while True:
            await agen.__anext__()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(_drain(), timeout=_ANEXT_TIMEOUT)


async def test_raw_group_key_filters_out_records_for_unwanted_groups(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    spec = _make_spec(stream_reader_stream_key)
    agen = subscribe(spec, frozenset({"a"}))
    try:
        await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        await redis_client.xadd(stream_reader_stream_key, {"group": "b", "seq": "1"})
        await redis_client.xadd(stream_reader_stream_key, {"group": "a", "seq": "2"})
        batch = await _next_batch(agen)
        assert batch == [("a", 2)]
    finally:
        await agen.aclose()


async def test_cursor_starts_at_tail_and_ignores_entries_added_before_start(
    settings: Settings,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 1.0
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 0.1

    key = stream_reader_stream_key
    await redis_client.xadd(key, {"group": "a", "seq": "0"})

    spec = _make_spec(key)
    first_agen = subscribe(spec, frozenset({"a"}))
    try:
        first_event = await asyncio.wait_for(
            first_agen.__anext__(),
            timeout=_ANEXT_TIMEOUT,
        )
        assert first_event is HEARTBEAT  # запись до старта хаба не видна никому

        await redis_client.xadd(key, {"group": "a", "seq": "1"})

        late_agen = subscribe(spec, frozenset({"a"}))
        try:
            await redis_client.xadd(key, {"group": "a", "seq": "2"})

            late_batch = await _next_batch(late_agen)
            assert late_batch == [("a", 1), ("a", 2)]

            await redis_client.xadd(key, {"group": "a", "seq": "3"})
            next_batch = await _next_batch(late_agen)
            assert next_batch == [("a", 3)]
        finally:
            await late_agen.aclose()
    finally:
        await first_agen.aclose()


async def test_malformed_record_is_skipped_without_blocking_rest_of_batch(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = _make_spec(stream_reader_stream_key)
    agen = subscribe(spec, frozenset({"a"}))
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
    agen = subscribe(spec, frozenset({"a"}))
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
    agen = subscribe(spec, frozenset({"a"}))

    await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)

    await asyncio.wait_for(agen.aclose(), timeout=_ANEXT_TIMEOUT)

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()


async def test_subscription_filtering_does_not_change_per_ticker_selection(
    settings: Settings,
    redis_client: Redis,
) -> None:
    """
    Тот же поток записей на группу "a" на двух хабах — один, где "a"
    смотрят в одиночку, другой, где рядом активно пишут "b"/"c" — должен
    давать подписчику "a" идентичную пачку. `rule` применяется на хабе один
    раз на группу и не видит ни другие группы, ни список подписчиков
    (design.md), поэтому равенство — не совпадение, а прямое следствие
    архитектуры.
    """
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 0.3
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 2.0
    top_n = 2

    solo_key = f"test-stream-reader-solo-{uuid.uuid4()}"
    crowded_key = f"test-stream-reader-crowded-{uuid.uuid4()}"
    solo_spec = _make_spec(solo_key, n=top_n)
    crowded_spec = _make_spec(crowded_key, n=top_n)

    solo_agen = subscribe(solo_spec, frozenset({"a"}))
    a_agen = subscribe(crowded_spec, frozenset({"a"}))
    b_agen = subscribe(crowded_spec, frozenset({"b"}))
    c_agen = subscribe(crowded_spec, frozenset({"c"}))
    try:
        await asyncio.wait_for(solo_agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        await asyncio.wait_for(a_agen.__anext__(), timeout=_ANEXT_TIMEOUT)

        for seq in range(1, 5):
            await redis_client.xadd(solo_key, {"group": "a", "seq": str(seq)})
            await redis_client.xadd(crowded_key, {"group": "a", "seq": str(seq)})
        for group in ("b", "c"):
            for seq in range(1, 5):
                await redis_client.xadd(crowded_key, {"group": group, "seq": str(seq)})

        solo_batch = await _next_batch(solo_agen)
        crowded_batch = await _next_batch(a_agen)

        assert solo_batch == crowded_batch
        assert len(solo_batch) == top_n
    finally:
        await solo_agen.aclose()
        await a_agen.aclose()
        await b_agen.aclose()
        await c_agen.aclose()


async def test_heartbeat_independent_of_other_subscribers_activity(
    settings: Settings,
    redis_client: Redis,
) -> None:
    """Requirement: heartbeat is per-subscriber, independent of other subscribers."""
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 0.05
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 0.15
    stream_key = f"test-stream-reader-{uuid.uuid4()}"
    spec = _make_spec(stream_key)

    quiet_agen = subscribe(spec, frozenset({"quiet"}))
    busy_agen = subscribe(spec, frozenset({"busy"}))
    try:
        await asyncio.wait_for(quiet_agen.__anext__(), timeout=_ANEXT_TIMEOUT)
        await asyncio.wait_for(busy_agen.__anext__(), timeout=_ANEXT_TIMEOUT)

        async def keep_busy() -> None:
            for seq in range(20):
                await redis_client.xadd(stream_key, {"group": "busy", "seq": str(seq)})
                await asyncio.sleep(0.02)

        busy_task = asyncio.ensure_future(keep_busy())
        try:
            quiet_event = await asyncio.wait_for(
                quiet_agen.__anext__(),
                timeout=_ANEXT_TIMEOUT,
            )
            assert quiet_event is HEARTBEAT
        finally:
            busy_task.cancel()
            with suppress(asyncio.CancelledError):
                await busy_task
    finally:
        await quiet_agen.aclose()
        await busy_agen.aclose()


async def test_slow_subscriber_receives_only_latest_batch(
    settings: Settings,
    redis_client: Redis,
) -> None:
    """Requirement: Bounded most-recent delivery per subscriber (drop-oldest)."""
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 0.05
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 2.0
    stream_key = f"test-stream-reader-{uuid.uuid4()}"
    spec = _make_spec(stream_key)
    agen = subscribe(spec, frozenset({"a"}))
    try:
        await asyncio.wait_for(agen.__anext__(), timeout=_ANEXT_TIMEOUT)

        await redis_client.xadd(stream_key, {"group": "a", "seq": "1"})
        await asyncio.sleep(0.15)  # первое окно закрылось, пачка не забрана
        await redis_client.xadd(stream_key, {"group": "a", "seq": "2"})
        await asyncio.sleep(0.15)  # второе окно перетёрло непрочитанную пачку

        batch = await _next_batch(agen)
        assert batch == [("a", 2)]
    finally:
        await agen.aclose()


async def test_upstream_failure_closes_all_subscribers(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    """Requirement: Upstream failure closes all subscribers on that stream."""

    def failing_rule(_items: Sequence[_Item]) -> list[_Item]:
        message = "нетранзиентная ошибка отбора"
        raise RuntimeError(message)

    spec: LiveStreamSpec[_Item, str] = LiveStreamSpec(
        label="test-stream-reader-failure",
        stream_key=stream_reader_stream_key,
        raw_group_key=lambda fields: fields.get("group"),
        decode=_decode,
        order_key=_order_key,
        rule=failing_rule,
    )
    agen_a = subscribe(spec, frozenset({"a"}))
    agen_b = subscribe(spec, frozenset({"b"}))
    try:
        await asyncio.wait_for(agen_a.__anext__(), timeout=_ANEXT_TIMEOUT)
        await asyncio.wait_for(agen_b.__anext__(), timeout=_ANEXT_TIMEOUT)

        await redis_client.xadd(stream_reader_stream_key, {"group": "a", "seq": "1"})

        await _wait_until_closed(agen_a)
        await _wait_until_closed(agen_b)
    finally:
        await agen_a.aclose()
        await agen_b.aclose()


async def test_hub_lifecycle_shared_and_torn_down_after_last_subscriber(
    fast_stream_reader_sse_settings: None,
    redis_client: Redis,
    stream_reader_stream_key: str,
) -> None:
    """Requirement: Upstream connection cost independent of subscriber count."""
    spec = _make_spec(stream_reader_stream_key)
    assert stream_reader_stream_key not in hub_module._hubs  # noqa: SLF001

    agen1 = subscribe(spec, frozenset({"a"}))
    await asyncio.wait_for(agen1.__anext__(), timeout=_ANEXT_TIMEOUT)
    hub1 = hub_module._hubs[stream_reader_stream_key]  # noqa: SLF001
    assert hub1.subscriber_count == 1

    agen2 = subscribe(spec, frozenset({"b"}))
    await asyncio.wait_for(agen2.__anext__(), timeout=_ANEXT_TIMEOUT)
    assert hub_module._hubs[stream_reader_stream_key] is hub1  # noqa: SLF001
    assert hub1.subscriber_count == 2  # noqa: PLR2004

    await agen1.aclose()
    assert hub_module._hubs[stream_reader_stream_key] is hub1  # noqa: SLF001
    assert hub1.subscriber_count == 1

    await agen2.aclose()
    assert stream_reader_stream_key not in hub_module._hubs  # noqa: SLF001

    agen3 = subscribe(spec, frozenset({"a"}))
    try:
        await asyncio.wait_for(agen3.__anext__(), timeout=_ANEXT_TIMEOUT)
        hub2 = hub_module._hubs[stream_reader_stream_key]  # noqa: SLF001
        assert hub2 is not hub1
    finally:
        await agen3.aclose()
