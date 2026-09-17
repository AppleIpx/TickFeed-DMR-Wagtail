"""Сборка меток времени ISS MOEX в aware UTC `datetime`.

ISS отдаёт время данных в двух разных формах, которые легко перепутать:

- в снимке борда (`marketdata`) — `UPDATETIME`, **только время без даты**
  (например, `"12:44:28"`); дату для него нужно брать из торгового дня
  отдельно. `SYSTIME` в этом же ответе — время формирования ответа
  сервером, а не время данных, и на живой проверке отставало от
  `UPDATETIME` на ~15 минут — использовать его для времени снимка нельзя.
- в ленте сделок — `SYSTIME` уже содержит полную дату и время
  (`"2026-09-08 12:44:28"`) и берётся напрямую как метка времени сделки.

Обе строки — naive и подразумевают часовой пояс `Europe/Moscow` (торговый
часовой пояс MOEX; `CELERY_TIMEZONE` в `config/settings/base.py` выставлен
в тот же пояс по той же причине — расписание/данные биржи, а не серверное
время). Проект работает в `USE_TZ=True`/`TIME_ZONE="UTC"` (ruff `DTZ` не
пропустит naive `datetime` в остальном коде), поэтому обе функции здесь
возвращают aware `datetime` в UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from datetime import date

MOSCOW_TZ = settings.MOSCOW_TZ


def board_updatetime_to_utc(trading_day: date, updatetime: str) -> datetime:
    """Собрать aware UTC `datetime` из даты торгового дня и `UPDATETIME` борда.

    `updatetime` — строка вида `"HH:MM:SS"` без даты (см. модульный
    докстринг: это время данных, в отличие от `SYSTIME` этого же ответа,
    которое сюда передавать нельзя).
    """
    hour, minute, second = (int(part) for part in updatetime.split(":"))
    moscow_time = datetime(
        trading_day.year,
        trading_day.month,
        trading_day.day,
        hour,
        minute,
        second,
        tzinfo=MOSCOW_TZ,
    )
    return moscow_time.astimezone(UTC)


def moscow_timestamp_to_utc(value: str) -> datetime:
    """Разобрать полную naive-метку времени MOEX (`SYSTIME` ленты сделок) в UTC."""
    naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007 -- см. .replace ниже
    return naive.replace(tzinfo=MOSCOW_TZ).astimezone(UTC)
