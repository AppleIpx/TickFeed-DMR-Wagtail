from django.conf import settings

from tickfeeddmr.ai.api.schemas.status import AiStatusOut, AiUsageOut
from tickfeeddmr.ai.services.dates import moscow_today
from tickfeeddmr.ai.services.quota.client import open_quota
from tickfeeddmr.ai.services.quota.reset import next_reset


async def _usage_out() -> AiUsageOut | None:
    async with open_quota() as quota:
        snapshot = await quota.snapshot()
    if snapshot is None:
        return None
    return AiUsageOut(
        requests=snapshot.requests,
        requests_limit=settings.AI_DAILY_REQUEST_LIMIT,
        tokens=snapshot.tokens,
        tokens_limit=settings.AI_DAILY_TOKEN_LIMIT,
        resets_at=next_reset(moscow_today()),
    )


async def status_out() -> AiStatusOut:
    """Статус ИИ; при выключенном ИИ или сбое Redis `usage` — `None`."""
    enabled = settings.AI_ENABLED
    return AiStatusOut(
        enabled=enabled,
        model=settings.AI_MODEL if enabled else None,
        max_messages=settings.AI_MAX_HISTORY_MESSAGES,
        max_message_chars=settings.AI_MAX_MESSAGE_CHARS,
        usage=await _usage_out() if enabled else None,
    )
