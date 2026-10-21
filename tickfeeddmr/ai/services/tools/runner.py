import logging
from typing import TYPE_CHECKING

import msgspec
from django.conf import settings

from config.api_base import DomainError, close_db_connections
from tickfeeddmr.ai.services.dates import moscow_today
from tickfeeddmr.ai.services.tools.errors import ToolInputError
from tickfeeddmr.ai.services.tools.registry import TOOLS
from tickfeeddmr.ai.services.tools.schemas import (
    PreparedCall,
    ToolContext,
    ToolErrorResult,
)

if TYPE_CHECKING:
    from tickfeeddmr.ai.services.llm.schemas import ToolCallRequest

logger = logging.getLogger(__name__)


def prepare_tool_call(call: ToolCallRequest) -> PreparedCall | ToolErrorResult:
    """Найти инструмент и разобрать аргументы; ошибка — результат для модели."""
    definition = TOOLS.get(call.name)
    if definition is None:
        return ToolErrorResult(
            f"Неизвестный инструмент {call.name}",
            hint=f"Доступны: {', '.join(TOOLS)}",
        )
    try:
        args = msgspec.json.decode(
            call.arguments_json or "{}",
            type=definition.args_type,
        )
    except msgspec.ValidationError as exc:
        return ToolErrorResult(f"Неверные аргументы: {exc}")
    except msgspec.DecodeError:
        return ToolErrorResult("Аргументы — не JSON")
    return PreparedCall(call, definition, args, definition.label(args))


def error_result_json(err: ToolErrorResult) -> str:
    """Результат-ошибка в виде JSON-строки для сообщения `tool`."""
    return msgspec.json.encode(err).decode()


def make_tool_context() -> ToolContext:
    """Контекст вызова: сегодняшняя дата по Москве и лимит строк из настроек."""
    return ToolContext(today=moscow_today(), max_rows=settings.AI_TOOL_MAX_ROWS)


async def execute_tool(prepared: PreparedCall, ctx: ToolContext) -> str:
    """Выполнить инструмент; любой сбой — JSON-ошибка, соединения БД закрыты."""
    try:
        result: msgspec.Struct = await prepared.definition.handler(prepared.args, ctx)
    except ToolInputError as exc:
        result = ToolErrorResult(exc.message, exc.hint)
    except DomainError as exc:
        result = ToolErrorResult(str(exc))
    except Exception:
        logger.exception("Инструмент %s завершился ошибкой", prepared.definition.name)
        result = ToolErrorResult("Внутренняя ошибка инструмента")
    finally:
        await close_db_connections()
    return msgspec.json.encode(result).decode()
