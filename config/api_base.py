from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from asgiref.sync import sync_to_async
from django.db import connections
from dmr import Controller
from dmr.errors import ErrorType
from dmr.plugins.msgspec import MsgspecSerializer
from dmr.streaming.sse import SSEController

if TYPE_CHECKING:
    from django.http import HttpResponse
    from dmr.endpoint import Endpoint


class DomainError(Exception):
    """Базовый класс доменных ошибок API — общий для всех приложений проекта."""

    status_code: ClassVar[HTTPStatus]


class _DomainErrorHandling:
    """Перевод `DomainError` в ответ — общий для обычных и SSE-контроллеров."""

    async def handle_async_error(
        self,
        endpoint: Endpoint,
        controller: Controller[MsgspecSerializer],
        exc: Exception,
    ) -> HttpResponse:
        """Перевести `DomainError` в ответ формата DMR `ErrorModel`.

        Любое исключение, не являющееся `DomainError`, пробрасывается
        дальше без изменений — этот метод отвечает только за доменные
        ошибки API, а не за общую обработку сбоев.
        """
        if not isinstance(exc, DomainError):
            raise  # noqa: PLE0704
        error_type = (
            ErrorType.not_found
            if exc.status_code == HTTPStatus.NOT_FOUND
            else ErrorType.user_msg
        )
        return controller.to_error(
            controller.format_error(str(exc), error_type=error_type),
            status_code=exc.status_code,
        )


class BaseController(_DomainErrorHandling, Controller[MsgspecSerializer]):
    """Общий базовый контроллер: сериализация через msgspec"""

    serializer = MsgspecSerializer


class BaseSSEController(_DomainErrorHandling, SSEController[MsgspecSerializer]):
    """Общий базовый SSE-контроллер: msgspec, `DomainError`, освобождение БД."""

    serializer = MsgspecSerializer
    streaming_ping_seconds = None  # type: ignore[assignment]

    @staticmethod
    async def release_db_connections() -> None:
        """Закрыть соединения с БД, открытые проверкой тикеров в начале ручки.

        Django закрывает соединение по `request_finished`, а для SSE это
        момент ухода клиента — то есть часы. Без явного закрытия каждый
        открытый стрим держал бы соединение с Postgres всё время жизни.
        Именно безусловный `close_all()`, а не `close_old_connections()`: тот
        закрывает только «просроченные», а в production `CONN_MAX_AGE=60`,
        так что живое соединение осталось бы открытым. `sync_to_async` идёт в
        том же потоке, где async ORM держит соединение запроса. После вызова
        генератор потока не должен обращаться к ORM.
        """
        await sync_to_async(connections.close_all)()
