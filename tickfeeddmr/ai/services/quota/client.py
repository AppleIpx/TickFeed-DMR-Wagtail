from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from django.conf import settings
from redis.asyncio import Redis

from tickfeeddmr.ai.services.quota.counter import DailyQuota

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def open_quota() -> AsyncIterator[DailyQuota]:
    """Счётчик на отдельном Redis-клиенте (db 0), закрываемом на выходе."""
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield DailyQuota(client)
    finally:
        await client.aclose()
