from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.quota.tokens import estimate_tokens

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.ai.services.chat.step import StepResult
    from tickfeeddmr.ai.services.llm.schemas import ChatMessage


class StepTokens:
    """Токены шага: от провайдера или оценка по символам."""

    __slots__ = ("completion", "estimated", "prompt")

    def __init__(self, prompt: int, completion: int, *, estimated: bool) -> None:
        self.prompt = prompt
        self.completion = completion
        self.estimated = estimated

    @property
    def total(self) -> int:
        return self.prompt + self.completion


def _message_chars(message: ChatMessage) -> int:
    calls = sum(len(c.arguments_json) + len(c.name) for c in message.tool_calls)
    return len(message.content) + calls


def step_tokens(messages: Sequence[ChatMessage], result: StepResult) -> StepTokens:
    """Расход шага: `usage` провайдера, а без него — оценка входа и выхода."""
    if result.usage is not None:
        return StepTokens(
            result.usage.prompt_tokens,
            result.usage.completion_tokens,
            estimated=False,
        )
    prompt_chars = sum(_message_chars(m) for m in messages)
    completion_chars = len(result.text) + sum(
        len(c.arguments_json) + len(c.name) for c in result.calls
    )
    return StepTokens(
        estimate_tokens(prompt_chars),
        estimate_tokens(completion_chars),
        estimated=True,
    )
