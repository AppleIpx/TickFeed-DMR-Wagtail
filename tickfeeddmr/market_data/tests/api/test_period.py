from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings

from tickfeeddmr.market_data.services.queries.errors import InvalidPeriodError
from tickfeeddmr.market_data.services.queries.period import resolve_period

_TODAY = date(2026, 9, 18)


def _frozen_today():
    return patch(
        "tickfeeddmr.market_data.services.queries.period.datetime",
        **{"now.return_value": datetime(2026, 9, 18, 12, tzinfo=UTC)},
    )


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=365)
def test_resolve_period_uses_configured_default_when_omitted() -> None:
    with _frozen_today():
        frm, to = resolve_period(date_from=None, date_to=None)

    assert to == _TODAY
    assert frm == _TODAY - timedelta(days=365)


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=365)
def test_resolve_period_configured_default_ignores_earliest_available() -> None:
    with _frozen_today():
        frm, to = resolve_period(
            date_from=None,
            date_to=None,
            earliest_available=date(2017, 8, 17),
        )

    assert to == _TODAY
    assert frm == _TODAY - timedelta(days=365)


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
def test_resolve_period_falls_back_to_earliest_available_when_unconfigured() -> None:
    with _frozen_today():
        frm, to = resolve_period(
            date_from=None,
            date_to=None,
            earliest_available=date(2017, 8, 17),
        )

    assert to == _TODAY
    assert frm == date(2017, 8, 17)


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
def test_resolve_period_collapses_to_single_day_when_no_data_at_all() -> None:
    """Ни настройки, ни хотя бы одной точки данных у актива — не ошибка.

    Окно схлопывается в `resolved_to`, вызывающий получает пустую историю
    тем же путём, что и любой другой непересекающийся период.
    """
    with _frozen_today():
        frm, to = resolve_period(date_from=None, date_to=None, earliest_available=None)

    assert frm == to == _TODAY


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
def test_resolve_period_explicit_date_from_wins_over_earliest_available() -> None:
    frm, to = resolve_period(
        date_from=date(2024, 1, 1),
        date_to=date(2024, 12, 31),
        earliest_available=date(2017, 8, 17),
    )

    assert frm == date(2024, 1, 1)
    assert to == date(2024, 12, 31)


def test_resolve_period_from_greater_than_to_raises() -> None:
    with pytest.raises(InvalidPeriodError):
        resolve_period(date_from=date(2026, 9, 18), date_to=date(2026, 9, 1))


def test_resolve_period_from_equal_to_to_is_not_an_error() -> None:
    frm, to = resolve_period(date_from=date(2026, 9, 18), date_to=date(2026, 9, 18))

    assert frm == to == date(2026, 9, 18)
