import asyncio
import logging
from typing import TYPE_CHECKING, Literal

from django.conf import settings

from tickfeeddmr.ai.services.chat.accounting import (
    estimate_step_reservation,
    step_tokens,
)
from tickfeeddmr.ai.services.chat.events import DoneEvent, ErrorEvent
from tickfeeddmr.ai.services.chat.prompt import build_system_prompt
from tickfeeddmr.ai.services.chat.run_stats import RunStats, log_summary
from tickfeeddmr.ai.services.chat.step import StepResult, stream_step
from tickfeeddmr.ai.services.chat.tool_step import run_tool_calls
from tickfeeddmr.ai.services.chat.user_messages import (
    INTERNAL_ERROR_MESSAGE,
    user_message,
)
from tickfeeddmr.ai.services.errors import AiQuotaExceededError, AiUnavailableError
from tickfeeddmr.ai.services.llm.exceptions import LLMError
from tickfeeddmr.ai.services.llm.schemas import ChatMessage
from tickfeeddmr.ai.services.tools.registry import tool_specs
from tickfeeddmr.ai.services.tools.runner import make_tool_context

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from datetime import date

    from tickfeeddmr.ai.services.chat.events import ChatEvent
    from tickfeeddmr.ai.services.llm.base import LLMProvider
    from tickfeeddmr.ai.services.quota.counter import DailyQuota

logger = logging.getLogger(__name__)

NO_ANSWER_MESSAGE = "Модель не смогла сформулировать ответ"


async def _steps(
    history: Sequence[ChatMessage],
    *,
    provider: LLMProvider,
    quota: DailyQuota,
    today: date,
    stats: RunStats,
) -> AsyncIterator[ChatEvent]:
    deadline = asyncio.get_running_loop().time() + settings.AI_CHAT_DEADLINE_SECONDS
    messages = [ChatMessage("system", build_system_prompt(today)), *history]
    specs = tool_specs()
    ctx = make_tool_context()
    max_steps = settings.AI_MAX_TOOL_ITERATIONS

    for step in range(1, max_steps + 1):
        final = step == max_steps
        reserved = await quota.reserve_step(estimate_step_reservation(messages))
        stats.steps = step

        result: StepResult | None = None
        async for item in stream_step(
            provider,
            messages,
            specs,
            final=final,
            deadline=deadline,
        ):
            if isinstance(item, StepResult):
                result = item
            else:
                yield item
        if result is None:
            return

        tokens = step_tokens(messages, result)
        stats.add_step(tokens)
        await quota.settle_step(reserved, tokens.total)

        if not result.calls:
            yield DoneEvent(stats.model)
            return
        if final:
            if result.text:
                yield DoneEvent(stats.model)
            else:
                yield ErrorEvent(NO_ANSWER_MESSAGE)
            return

        stats.add_calls(result.calls)
        messages.append(
            ChatMessage("assistant", result.text, tool_calls=result.calls),
        )
        async for item in run_tool_calls(result.calls, ctx, deadline):
            if isinstance(item, ChatMessage):
                messages.append(item)
            else:
                yield item


async def run_chat(
    history: Sequence[ChatMessage],
    *,
    provider: LLMProvider,
    model: str,
    quota: DailyQuota,
    today: date,
) -> AsyncIterator[ChatEvent]:
    """Цикл «модель ↔ инструменты»: доменные события, в конце — сводка."""
    stats = RunStats(model)
    outcome: Literal["done", "error"] = "error"
    error: str | None = None
    try:
        async for event in _steps(
            history,
            provider=provider,
            quota=quota,
            today=today,
            stats=stats,
        ):
            if isinstance(event, DoneEvent):
                outcome = "done"
            elif isinstance(event, ErrorEvent):
                error = event.message
            yield event
    except (AiQuotaExceededError, AiUnavailableError, LLMError, TimeoutError) as exc:
        logger.warning("ИИ-чат: прогон прерван: %s: %s", type(exc).__name__, exc)
        error = user_message(exc)
        yield ErrorEvent(error)
    except Exception:
        logger.exception("ИИ-чат: непредвиденная ошибка")
        error = INTERNAL_ERROR_MESSAGE
        yield ErrorEvent(error)

    summary = stats.summary(outcome, error)
    log_summary(
        summary,
        quota.last_usage,
        request_limit=settings.AI_DAILY_REQUEST_LIMIT,
        token_limit=settings.AI_DAILY_TOKEN_LIMIT,
    )
    yield summary
