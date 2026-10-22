import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.conf import settings
from redis.exceptions import RedisError

from tickfeeddmr.ai.services.dates import moscow_today
from tickfeeddmr.ai.services.errors import AiQuotaExceededError, AiUnavailableError
from tickfeeddmr.ai.services.quota.schemas import QuotaUsage

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from datetime import date

    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

KEY_TTL_SECONDS = 172_800
WARN_FRACTION = 0.8
_REQUESTS = "requests"
_TOKENS = "tokens"
_FLAG_WARNED_80 = "warned_80"
_FLAG_WARNED_EXHAUSTED = "warned_exhausted"
_UNAVAILABLE = "Не удалось проверить лимит ИИ"


@contextmanager
def _redis_guard() -> Iterator[None]:
    try:
        yield
    except (RedisError, OSError) as exc:
        raise AiUnavailableError(_UNAVAILABLE) from exc


def _to_int(value: str | None) -> int:
    return int(value) if value else 0


class DailyQuota:
    """Дневной счётчик обращений и токенов в Redis; сутки — по Москве."""

    def __init__(
        self,
        client: Redis,
        *,
        today: Callable[[], date] = moscow_today,
    ) -> None:
        self._client = client
        self._today = today
        self.last_usage: QuotaUsage | None = None

    def _key(self) -> str:
        return f"{settings.AI_QUOTA_KEY_PREFIX}:{self._today().isoformat()}"

    async def usage(self) -> QuotaUsage:
        with _redis_guard():
            requests, tokens = await self._client.hmget(self._key(), _REQUESTS, _TOKENS)
        self.last_usage = QuotaUsage(requests=_to_int(requests), tokens=_to_int(tokens))
        return self.last_usage

    async def snapshot(self) -> QuotaUsage | None:
        """Расход для статуса; при сбое Redis — `None`, без исключения."""
        try:
            return await self.usage()
        except AiUnavailableError:
            logger.warning("ИИ: не удалось прочитать расход из Redis", exc_info=True)
            return None

    async def ensure_available(self) -> None:
        usage = await self.usage()
        if (
            usage.requests < settings.AI_DAILY_REQUEST_LIMIT
            and usage.tokens < settings.AI_DAILY_TOKEN_LIMIT
        ):
            return
        if await self._set_flag(_FLAG_WARNED_EXHAUSTED):
            logger.warning(
                "ИИ: дневной лимит исчерпан (запросы %d/%d, токены %d/%d), "
                "чат отказывает до 00:00 МСК",
                usage.requests,
                settings.AI_DAILY_REQUEST_LIMIT,
                usage.tokens,
                settings.AI_DAILY_TOKEN_LIMIT,
            )
        msg = "Дневной лимит обращений к ИИ исчерпан, попробуйте завтра"
        raise AiQuotaExceededError(msg)

    async def count_request(self) -> None:
        await self._incr(_REQUESTS, 1)

    async def add_tokens(self, n: int) -> None:
        if n <= 0:
            return
        await self._incr(_TOKENS, n)
        usage = self.last_usage
        limit = settings.AI_DAILY_TOKEN_LIMIT
        if (
            usage is not None
            and usage.tokens >= WARN_FRACTION * limit
            and await self._set_flag(_FLAG_WARNED_80)
        ):
            logger.warning(
                "ИИ: израсходовано 80%% дневного лимита токенов (%d/%d)",
                usage.tokens,
                limit,
            )

    async def _incr(self, field: str, n: int) -> None:
        key = self._key()
        with _redis_guard():
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.hincrby(key, field, n)
                pipe.expire(key, KEY_TTL_SECONDS)
                pipe.hmget(key, _REQUESTS, _TOKENS)
                _, _, (requests, tokens) = await pipe.execute()
        self.last_usage = QuotaUsage(requests=_to_int(requests), tokens=_to_int(tokens))

    async def _set_flag(self, flag: str) -> bool:
        """`True`, если флаг выставлен впервые; сбой Redis не пробрасывается."""
        try:
            return bool(await self._client.hsetnx(self._key(), flag, 1))
        except RedisError, OSError:
            logger.warning("ИИ: не удалось выставить флаг %s", flag, exc_info=True)
            return False
