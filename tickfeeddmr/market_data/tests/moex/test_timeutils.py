"""Юнит-тесты сборки меток времени ISS MOEX (`providers/moex/timeutils.py`).

`Europe/Moscow` не переходит на летнее время с 2014 года, поэтому смещение
относительно UTC везде ниже фиксированное +3:00 — граничные случаи важны
только с точки зрения перехода через полночь/смену даты в UTC, не DST.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from tickfeeddmr.market_data.providers.moex.timeutils import (
    board_updatetime_to_utc,
    moscow_timestamp_to_utc,
)


def test_board_updatetime_to_utc_matches_verified_example() -> None:
    # Проверенный на живых данных пример из задания этапа 4.
    result = board_updatetime_to_utc(date(2026, 9, 8), "12:44:28")

    assert result == datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC)


def test_board_updatetime_to_utc_midnight_moscow_is_previous_day_utc() -> None:
    result = board_updatetime_to_utc(date(2026, 9, 8), "00:00:00")

    assert result == datetime(2026, 9, 7, 21, 0, 0, tzinfo=UTC)


def test_board_updatetime_to_utc_end_of_day_moscow() -> None:
    result = board_updatetime_to_utc(date(2026, 9, 8), "23:59:59")

    assert result == datetime(2026, 9, 8, 20, 59, 59, tzinfo=UTC)


def test_moscow_timestamp_to_utc_matches_verified_example() -> None:
    result = moscow_timestamp_to_utc("2026-09-08 12:44:28")

    assert result == datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC)


def test_moscow_timestamp_to_utc_crosses_utc_day_boundary() -> None:
    # 01:30 МСК 2026-09-08 -> ещё 2026-09-07 в UTC (смещение +3:00).
    result = moscow_timestamp_to_utc("2026-09-08 01:30:00")

    assert result == datetime(2026, 9, 7, 22, 30, 0, tzinfo=UTC)
