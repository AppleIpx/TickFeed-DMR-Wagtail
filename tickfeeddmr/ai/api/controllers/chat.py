from collections.abc import AsyncIterator  # noqa: TC003
from http import HTTPStatus

from django.conf import settings
from dmr import Body, ResponseSpec, modify
from dmr.errors import ErrorModel
from dmr.streaming.sse import SSEvent  # noqa: TC002

from config.api_base import BaseSSEController
from tickfeeddmr.ai.api.presenters.chat import chat_events
from tickfeeddmr.ai.api.schemas.chat import (  # noqa: TC001
    ChatEventOut,
    ChatRequestIn,
)
from tickfeeddmr.ai.api.tags import AI_TAGS
from tickfeeddmr.ai.services.chat.history import validate_history
from tickfeeddmr.ai.services.chat.schemas import HistoryMessage
from tickfeeddmr.ai.services.errors import AiDisabledError
from tickfeeddmr.ai.services.quota.client import open_quota


class AiChatController(BaseSSEController):
    """`POST /api/ai/chat` — ответ ИИ-аналитика потоком SSE.

    Выключенный ИИ, неверная история и исчерпанный лимит отдаются обычным
    JSON-ответом с кодом ошибки до начала потока.
    """

    @modify(
        tags=AI_TAGS,
        extra_responses=[
            ResponseSpec(ErrorModel, status_code=HTTPStatus.SERVICE_UNAVAILABLE),
            ResponseSpec(ErrorModel, status_code=HTTPStatus.TOO_MANY_REQUESTS),
        ],
    )
    async def post(
        self,
        parsed_body: Body[ChatRequestIn],
    ) -> AsyncIterator[SSEvent[ChatEventOut]]:
        if not settings.AI_ENABLED:
            msg = "ИИ-аналитик выключен"
            raise AiDisabledError(msg)
        history = validate_history(
            [HistoryMessage(m.role, m.content) for m in parsed_body.messages],
        )
        async with open_quota() as quota:
            await quota.ensure_available()
        await self.release_db_connections()
        return chat_events(history, model=settings.AI_MODEL)
