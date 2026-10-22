from dmr import modify

from config.api_base import BaseController
from tickfeeddmr.ai.api.presenters.status import status_out
from tickfeeddmr.ai.api.schemas.status import AiStatusOut  # noqa: TC001
from tickfeeddmr.ai.api.tags import AI_TAGS


class AiStatusController(BaseController):
    """`GET /api/ai/status` — включён ли ИИ, лимиты истории и расход за сегодня."""

    @modify(tags=AI_TAGS)
    async def get(self) -> AiStatusOut:
        return await status_out()
