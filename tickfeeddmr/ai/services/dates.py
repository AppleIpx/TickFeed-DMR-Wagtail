from datetime import UTC, date, datetime

from django.conf import settings


def moscow_today() -> date:
    """Сегодняшняя дата по Москве."""
    return datetime.now(UTC).astimezone(settings.MOSCOW_TZ).date()
