import asyncio
from typing import TYPE_CHECKING

from django.conf import settings

from tickfeeddmr.ai.services.chat.events import ToolCallEvent
from tickfeeddmr.ai.services.llm.schemas import ChatMessage
from tickfeeddmr.ai.services.tools.runner import (
    error_result_json,
    execute_tool,
    prepare_tool_call,
)
from tickfeeddmr.ai.services.tools.schemas import ToolErrorResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tickfeeddmr.ai.services.llm.schemas import ToolCallRequest
    from tickfeeddmr.ai.services.tools.schemas import ToolContext

TOO_MANY_CALLS = "Слишком много вызовов за один шаг"


async def run_tool_calls(
    calls: Sequence[ToolCallRequest],
    ctx: ToolContext,
    deadline: float,
) -> AsyncIterator[ToolCallEvent | ChatMessage]:
    """Выполнить вызовы шага; каждому `id` достаётся `tool`-сообщение."""
    for index, call in enumerate(calls):
        if index >= settings.AI_MAX_TOOL_CALLS_PER_STEP:
            result = error_result_json(ToolErrorResult(TOO_MANY_CALLS))
        else:
            prepared = prepare_tool_call(call)
            if isinstance(prepared, ToolErrorResult):
                result = error_result_json(prepared)
            else:
                yield ToolCallEvent(call.name, prepared.label, call.arguments_json)
                async with asyncio.timeout_at(deadline):
                    result = await execute_tool(prepared, ctx)
        yield ChatMessage("tool", result, tool_call_id=call.id, name=call.name)
