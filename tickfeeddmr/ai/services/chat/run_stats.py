import logging
import time
from typing import TYPE_CHECKING, Literal

from tickfeeddmr.ai.services.chat.events import RunSummaryEvent, ToolCallRecord

if TYPE_CHECKING:
    from tickfeeddmr.ai.services.chat.accounting import StepTokens
    from tickfeeddmr.ai.services.llm.schemas import ToolCallRequest
    from tickfeeddmr.ai.services.quota.schemas import QuotaUsage

logger = logging.getLogger(__name__)

_THOUSAND = 1000


def format_tokens(n: int) -> str:
    """`98765` → `99k`, малые числа — как есть."""
    return f"{round(n / _THOUSAND)}k" if n >= _THOUSAND else str(n)


class RunStats:
    """Накопитель сведений о прогоне для сводки и итоговой строки лога."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.steps = 0
        self.tool_calls: list[ToolCallRecord] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.tokens_estimated = False
        self._started = time.monotonic()

    def add_step(self, tokens: StepTokens) -> None:
        self.prompt_tokens += tokens.prompt
        self.completion_tokens += tokens.completion
        self.tokens_estimated = self.tokens_estimated or tokens.estimated

    def add_calls(self, calls: tuple[ToolCallRequest, ...]) -> None:
        self.tool_calls.extend(ToolCallRecord(c.name, c.arguments_json) for c in calls)

    def summary(
        self,
        outcome: Literal["done", "error"],
        error: str | None,
    ) -> RunSummaryEvent:
        return RunSummaryEvent(
            model=self.model,
            steps=self.steps,
            tool_calls=self.tool_calls,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            tokens_estimated=self.tokens_estimated,
            duration_seconds=time.monotonic() - self._started,
            outcome=outcome,
            error=error,
        )


def log_summary(
    summary: RunSummaryEvent,
    usage: QuotaUsage | None,
    *,
    request_limit: int,
    token_limit: int,
) -> None:
    """Одна INFO-строка о прогоне без текста диалога."""
    today = (
        f"{usage.requests}/{request_limit} запросов, "
        f"{format_tokens(usage.tokens)}/{format_tokens(token_limit)} токенов"
        if usage is not None
        else "н/д"
    )
    names = ",".join(c.name for c in summary.tool_calls) or "-"
    logger.info(
        "ИИ-чат: модель=%s шагов=%d инструменты=%s токены=%d+%d%s "
        "длительность=%.1fс исход=%s | сегодня: %s",
        summary.model,
        summary.steps,
        names,
        summary.prompt_tokens,
        summary.completion_tokens,
        " (оценка)" if summary.tokens_estimated else "",
        summary.duration_seconds,
        summary.outcome,
        today,
    )
