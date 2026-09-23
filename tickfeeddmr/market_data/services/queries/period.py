from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db.models import Min

from tickfeeddmr.market_data.services.queries.errors import InvalidPeriodError
from tickfeeddmr.market_data.services.queries.settings import (
    validate_history_default_period_days,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet

MOSCOW_TZ = settings.MOSCOW_TZ

validate_history_default_period_days(settings.MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS)


def resolve_period(
    *,
    date_from: date | None,
    date_to: date | None,
    earliest_available: date | None = None,
) -> tuple[date, date]:
    """Разрешить `(from, to)` с умолчаниями.

    `date_from`, если не передан клиентом, берётся так:
    - `settings.MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS` задана — «сегодня
      минус N дней», как раньше;
    - не задана — `earliest_available` (самая ранняя дата, которая реально
      есть в БД у конкретного актива — считает вызывающий, эта функция
      ничего не знает про модели). Если и `earliest_available` нет (у
      актива в БД ещё нет ни одной точки данных), окно схлопывается в
      единственный день `resolved_to` — вызывающий получит на выходе
      пустую историю тем же путём, что и любой другой непересекающийся
      период, а не отдельной ошибкой.

    Поднимает `InvalidPeriodError`, если `from` больше `to`.
    """
    today = datetime.now(UTC).astimezone(MOSCOW_TZ).date()
    resolved_to = date_to or today
    default_period_days = settings.MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS
    if date_from is not None:
        resolved_from = date_from
    elif default_period_days is not None:
        resolved_from = resolved_to - timedelta(days=default_period_days)
    else:
        resolved_from = earliest_available or resolved_to
    if resolved_from > resolved_to:
        msg = f"`from` ({resolved_from}) не может быть позже `to` ({resolved_to})"
        raise InvalidPeriodError(msg)
    return resolved_from, resolved_to


async def resolve_earliest_available(
    *,
    date_from: date | None,
    queryset: QuerySet[Any],
    field_name: str,
) -> date | None:
    """`Min(field_name)` по `queryset`, только если `resolve_period` его учтёт.

    Считать агрегат имеет смысл лишь тогда, когда `date_from` не передан
    клиентом и `MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS` не задана — в
    любом другом случае `resolve_period` результат проигнорирует, а поход
    в БД был бы впустую. `queryset`/`field_name` — доменное знание вызывающего
    (какая модель, какое поле даты); эта функция его не имеет.
    """
    default_period_days = settings.MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS
    if date_from is not None or default_period_days is not None:
        return None
    return (await queryset.aaggregate(Min(field_name)))[f"{field_name}__min"]
