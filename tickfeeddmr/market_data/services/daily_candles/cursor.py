from datetime import date, datetime, timedelta

from django.conf import settings

MOSCOW_TZ = settings.MOSCOW_TZ


def moscow_yesterday(*, now: datetime) -> date:
    """Вчера по Москве относительно `now` (aware `datetime`)."""
    return now.astimezone(MOSCOW_TZ).date() - timedelta(days=1)


def is_up_to_date(last_date: date | None, *, until: date) -> bool:
    """Есть ли уже свеча за `until` или позже — тогда догонять нечего."""
    return last_date is not None and last_date >= until
