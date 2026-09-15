from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from django.db.models import Q

from tickfeeddmr.market_data.services.queries.errors import InvalidCursorError
from tickfeeddmr.market_data.services.queries.types import Cursor

if TYPE_CHECKING:
    from django.db.models import QuerySet

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


class _TimestampedRow(Protocol):
    timestamp: datetime
    pk: int


def encode_cursor(*, timestamp: datetime, pk: int) -> str:
    """Собрать непрозрачную строку курсора из точки `(timestamp, pk)`."""
    raw = f"{timestamp.isoformat()}|{pk}"
    return urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> Cursor:
    """Разобрать курсор, полученный от клиента.

    `binascii.Error` (битый base64) и `UnicodeDecodeError` — оба подклассы
    `ValueError`, как и ошибки `split`/`int()`/`datetime.fromisoformat` —
    единственного `except ValueError` достаточно.
    """
    try:
        raw = urlsafe_b64decode(cursor.encode()).decode()
        timestamp_raw, pk_raw = raw.split("|")
        return Cursor(timestamp=datetime.fromisoformat(timestamp_raw), pk=int(pk_raw))
    except ValueError as exc:
        msg = f"Некорректный курсор: {cursor!r}"
        raise InvalidCursorError(msg) from exc


async def fetch_cursor_page(
    queryset: QuerySet[_TimestampedRow],
    *,
    cursor: Cursor | None,
    limit: int,
) -> tuple[list[_TimestampedRow], str | None]:
    """Прочитать одну страницу по убыванию `(timestamp, pk)`.

    `queryset` уже отфильтрован вызывающим кодом (актив, доп. условия) —
    эта функция накладывает только сортировку и границу курсора. Читает
    `limit + 1` строк, чтобы узнать, есть ли следующая страница, не делая
    отдельный `COUNT`.
    """
    qs = queryset
    if cursor is not None:
        qs = qs.filter(
            Q(timestamp__lt=cursor.timestamp)
            | Q(timestamp=cursor.timestamp, pk__lt=cursor.pk),
        )
    rows = [row async for row in qs.order_by("-timestamp", "-pk")[: limit + 1]]
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_cursor(timestamp=last.timestamp, pk=last.pk)
    return page, next_cursor
