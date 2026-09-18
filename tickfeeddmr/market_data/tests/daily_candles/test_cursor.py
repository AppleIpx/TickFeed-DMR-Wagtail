from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tickfeeddmr.market_data.services.daily_candles.cursor import (
    is_up_to_date,
    moscow_yesterday,
)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 18, 0, 30, tzinfo=UTC), date(2026, 9, 17)),
        (datetime(2026, 9, 18, 23, 30, tzinfo=UTC), date(2026, 9, 18)),
    ],
)
def test_moscow_yesterday(now: datetime, expected: date) -> None:
    assert moscow_yesterday(now=now) == expected


@pytest.mark.parametrize(
    ("last_date", "until", "expected"),
    [
        (None, date(2026, 9, 17), False),
        (date(2026, 9, 16), date(2026, 9, 17), False),
        (date(2026, 9, 17), date(2026, 9, 17), True),
        (date(2026, 9, 18), date(2026, 9, 17), True),
    ],
)
def test_is_up_to_date(
    last_date: date | None,
    until: date,
    expected: bool,  # noqa: FBT001
) -> None:
    assert is_up_to_date(last_date, until=until) is expected
