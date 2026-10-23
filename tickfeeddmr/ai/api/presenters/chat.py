from contextlib import aclosing
from typing import TYPE_CHECKING

from tickfeeddmr.ai.api.presenters.chat_events import to_out, to_sse
from tickfeeddmr.ai.api.schemas.chat import ChatErrorOut
from tickfeeddmr.ai.services.chat.loop import run_chat
from tickfeeddmr.ai.services.dates import moscow_today
from tickfeeddmr.ai.services.errors import AiUnavailableError
from tickfeeddmr.ai.services.llm.factory import build_provider
from tickfeeddmr.ai.services.quota.client import open_quota

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from dmr.streaming.sse import SSEvent

    from tickfeeddmr.ai.api.schemas.chat import ChatEventOut
    from tickfeeddmr.ai.services.llm.schemas import ChatMessage


async def chat_events(
    history: Sequence[ChatMessage],
    *,
    model: str,
) -> AsyncIterator[SSEvent[ChatEventOut]]:
    """SSE-события ответа; провайдер и Redis-клиент живут, пока открыт поток."""
    provider = build_provider(model)
    try:
        async with open_quota() as quota:
            events = run_chat(
                history,
                provider=provider,
                model=model,
                quota=quota,
                today=moscow_today(),
            )
            async with aclosing(events):
                async for event in events:
                    out = to_out(event)
                    if out is not None:
                        yield to_sse(out)
    except AiUnavailableError as exc:
        yield to_sse(ChatErrorOut(message=str(exc)))
    finally:
        await provider.aclose()
