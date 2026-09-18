from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest

from tickfeeddmr.market_data.services.queries.errors import InvalidPeriodError
from tickfeeddmr.market_data.services.queries.period import (
    DEFAULT_PERIOD_DAYS,
    resolve_period,
)

_TODAY = date(2026, 9, 18)


def test_resolve_period_defaults_to_last_year_when_omitted() -> None:
    with patch(
        "tickfeeddmr.market_data.services.queries.period.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 9, 18, 12, tzinfo=UTC)
        frm, to = resolve_period(date_from=None, date_to=None)

    assert to == _TODAY
    assert frm == _TODAY - timedelta(days=DEFAULT_PERIOD_DAYS)


def test_resolve_period_from_greater_than_to_raises() -> None:
    with pytest.raises(InvalidPeriodError):
        resolve_period(date_from=date(2026, 9, 18), date_to=date(2026, 9, 1))


def test_resolve_period_from_equal_to_to_is_not_an_error() -> None:
    frm, to = resolve_period(date_from=date(2026, 9, 18), date_to=date(2026, 9, 18))

    assert frm == to == date(2026, 9, 18)
