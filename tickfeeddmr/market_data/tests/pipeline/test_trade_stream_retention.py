from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import patch

from tickfeeddmr.market_data.services import trade_stream_retention
from tickfeeddmr.market_data.services.trade_stream_retention import (
    TradeStreamTrimmer,
    stream_ceiling_minid,
)

if TYPE_CHECKING:
    import pytest
    from redis.asyncio import Redis

_MS_PER_SECOND = 1000
_TEST_EXECUTION_TOLERANCE_MS = 2000


def test_stream_ceiling_minid_is_now_minus_ceiling_in_milliseconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_now = 1_700_000_000.0
    monkeypatch.setattr(trade_stream_retention.time, "time", lambda: frozen_now)

    result = stream_ceiling_minid(ceiling_seconds=300)

    assert result == str(int(frozen_now * _MS_PER_SECOND) - 300 * _MS_PER_SECOND)


def test_stream_ceiling_minid_returns_a_plain_ms_string() -> None:
    result = stream_ceiling_minid(ceiling_seconds=60)

    assert result.isdigit()


async def test_maybe_trim_uses_last_written_boundary_when_it_is_older(
    redis_client: Redis,
    retention_stream_key: str,
) -> None:
    """`last_written` далеко в прошлом -> побеждает он, не `now - gap`."""
    trimmer = TradeStreamTrimmer(
        stream_key=retention_stream_key,
        gap_seconds=300,
        interval_seconds=0,  # интервал не в фокусе этого теста
    )
    old_ms = int(time.time() * _MS_PER_SECOND) - 1_000 * _MS_PER_SECOND
    trimmer.note_written(f"{old_ms}-0")

    with patch.object(redis_client, "xtrim", wraps=redis_client.xtrim) as spy:
        await trimmer.maybe_trim(redis_client)

    spy.assert_called_once_with(
        retention_stream_key,
        minid=str(old_ms),
        approximate=True,
    )


async def test_maybe_trim_uses_gap_boundary_when_last_written_is_recent(
    redis_client: Redis,
    retention_stream_key: str,
) -> None:
    """`last_written` только что -> побеждает `now - gap`, а не сама запись."""
    trimmer = TradeStreamTrimmer(
        stream_key=retention_stream_key,
        gap_seconds=300,
        interval_seconds=0,
    )
    recent_ms = int(time.time() * _MS_PER_SECOND) - 1 * _MS_PER_SECOND
    trimmer.note_written(f"{recent_ms}-0")

    with patch.object(redis_client, "xtrim", wraps=redis_client.xtrim) as spy:
        await trimmer.maybe_trim(redis_client)

    spy.assert_called_once()
    (_stream_key,), kwargs = spy.call_args
    boundary_ms = int(kwargs["minid"])
    expected = int(time.time() * _MS_PER_SECOND) - 300 * _MS_PER_SECOND
    # Небольшой допуск на время выполнения самого теста.
    assert abs(boundary_ms - expected) < _TEST_EXECUTION_TOLERANCE_MS
    assert boundary_ms < recent_ms


async def test_maybe_trim_is_a_no_op_within_interval(
    redis_client: Redis,
    retention_stream_key: str,
) -> None:
    trimmer = TradeStreamTrimmer(
        stream_key=retention_stream_key,
        gap_seconds=300,
        interval_seconds=60,
    )
    trimmer.note_written(f"{int(time.time() * _MS_PER_SECOND)}-0")
    trimmer._last_trim_at -= 100  # noqa: SLF001

    with patch.object(redis_client, "xtrim", wraps=redis_client.xtrim) as spy:
        await trimmer.maybe_trim(redis_client)
        await trimmer.maybe_trim(redis_client)

    spy.assert_called_once()


async def test_note_written_none_does_not_move_boundary(
    redis_client: Redis,
    retention_stream_key: str,
) -> None:
    trimmer = TradeStreamTrimmer(
        stream_key=retention_stream_key,
        gap_seconds=300,
        interval_seconds=0,
    )
    old_ms = int(time.time() * _MS_PER_SECOND) - 1_000 * _MS_PER_SECOND
    trimmer.note_written(f"{old_ms}-0")
    trimmer.note_written(None)  # не должно ничего сдвинуть

    with patch.object(redis_client, "xtrim", wraps=redis_client.xtrim) as spy:
        await trimmer.maybe_trim(redis_client)

    spy.assert_called_once_with(
        retention_stream_key,
        minid=str(old_ms),
        approximate=True,
    )


async def test_note_written_before_any_call_keeps_maybe_trim_a_no_op(
    redis_client: Redis,
    retention_stream_key: str,
) -> None:
    """До первой успешной записи (`_last_written is None`) обрезки быть не должно."""
    trimmer = TradeStreamTrimmer(
        stream_key=retention_stream_key,
        gap_seconds=300,
        interval_seconds=10,
    )

    with patch.object(redis_client, "xtrim", wraps=redis_client.xtrim) as spy:
        await trimmer.maybe_trim(redis_client)

    spy.assert_not_called()
