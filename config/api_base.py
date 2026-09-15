from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from dmr import Controller
from dmr.errors import ErrorType
from dmr.plugins.msgspec import MsgspecSerializer

if TYPE_CHECKING:
    from django.http import HttpResponse
    from dmr.endpoint import Endpoint


class DomainError(Exception):
    """Базовый класс доменных ошибок API — общий для всех приложений проекта."""

    status_code: ClassVar[HTTPStatus]


class BaseController(Controller[MsgspecSerializer]):
    """Общий базовый контроллер: сериализация через msgspec"""

    serializer = MsgspecSerializer

    async def handle_async_error(
        self,
        endpoint: Endpoint,
        controller: BaseController,
        exc: Exception,
    ) -> HttpResponse:
        """Перевести `DomainError` в ответ формата DMR `ErrorModel`.

        Формат ответа — встроенный `ErrorModel` DMR
        (`{"detail": [{"msg": ..., "type": ...}]}`), а не самописный
        RFC 9457: `PathComponent`/`QueryComponent` уже автоматически
        регистрируют для 404/422 схему именно такой формы
        (`dmr/components.py::ComponentParser.provide_response_specs`,
        `PathComponent.provide_response_specs`). DMR валидирует любой
        возвращаемый ответ против зарегистрированной для этого статус-кода
        схемы — свой формат (RFC 9457 или любой другой) требовал бы
        одновременно регистрировать `ResponseSpec` на каждом методе
        контроллера и **заменял бы** этим уже существующую схему, ломая
        штатные ошибки валидации самого DMR на том же статус-коде. Проще
        и безопаснее говорить на языке формата, который DMR и так ждёт.

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
