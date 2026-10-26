from datetime import date, datetime, time, timedelta

from django.conf import settings


def next_reset(today: date) -> datetime:
    """Ближайшая полночь по Москве после `today` (aware)."""
    return datetime.combine(
        today + timedelta(days=1),
        time.min,
        tzinfo=settings.MOSCOW_TZ,
    )
