from datetime import UTC, date, datetime, timedelta

from django.conf import settings

from tickfeeddmr.market_data.services.queries.errors import InvalidPeriodError

MOSCOW_TZ = settings.MOSCOW_TZ
DEFAULT_PERIOD_DAYS = 365


def resolve_period(
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    """Разрешить `(from, to)` с умолчаниями.

    Поднимает `InvalidPeriodError`, если `from` больше `to`.
    """
    today = datetime.now(UTC).astimezone(MOSCOW_TZ).date()
    resolved_to = date_to or today
    resolved_from = date_from or resolved_to - timedelta(days=DEFAULT_PERIOD_DAYS)
    if resolved_from > resolved_to:
        msg = f"`from` ({resolved_from}) не может быть позже `to` ({resolved_to})"
        raise InvalidPeriodError(msg)
    return resolved_from, resolved_to
