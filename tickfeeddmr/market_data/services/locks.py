"""Redis-лок `SET NX EX` для защиты периодических задач от наложения.

Общий хелпер для `market_data`-задач, чей прогон может длиться дольше
собственного интервала расписания (см. "Celery" в `CLAUDE.md` — правило
"Overlap protection"). Лок — доменный, а не брокерный: живёт на
`settings.REDIS_URL` (db 0), рядом с остальными ключами `market_data:*`
(включая Redis Stream сделок Binance), а не на `CELERY_BROKER_URL`
(db 1) — задача сама по себе не имеет отношения к очереди Celery.
"""

import logging
import secrets
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from redis.asyncio import Redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class LockBusyError(Exception):
    """Лок уже занят другим прогоном — вызывающая задача должна выйти, не упасть."""


_RELEASE_IF_OWNER_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


@asynccontextmanager
async def redis_lock(
    *,
    redis_url: str,
    key: str,
    ttl_seconds: int,
) -> AsyncIterator[None]:
    """Взять `key` через `SET NX EX <токен владельца>`, снять по выходу из блока.

    Не блокирует и не ждёт освобождения: если лок уже занят, сразу
    поднимает `LockBusyError` — вызывающая задача логирует, что прогон
    ещё идёт, и выходит, а не встаёт в очередь на выполнение.
    `ttl_seconds` — страховка на случай, если процесс с локом упадёт, не
    сняв его: следующий прогон не будет заблокирован навсегда.

    Освобождение — по случайному токену владельца (см.
    `_RELEASE_IF_OWNER_SCRIPT`), а не голым `DEL`: иначе исходный
    владелец, переживший свой TTL, мог бы на выходе из блока удалить уже
    чужой (следующий) лок.
    """
    token = secrets.token_hex(16)
    client: Redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        acquired = await client.set(key, token, nx=True, ex=ttl_seconds)
        if not acquired:
            raise LockBusyError(key)
        try:
            yield
        finally:
            await client.eval(_RELEASE_IF_OWNER_SCRIPT, 1, key, token)
    finally:
        await client.aclose()
