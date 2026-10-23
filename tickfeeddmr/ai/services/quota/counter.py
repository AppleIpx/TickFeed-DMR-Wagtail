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
    from typing import NoReturn

    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

KEY_TTL_SECONDS = 172_800
WARN_FRACTION = 0.8
_REQUESTS = "requests"
_TOKENS = "tokens"
_FLAG_WARNED_80 = "warned_80"
_FLAG_WARNED_EXHAUSTED = "warned_exhausted"
_UNAVAILABLE = "Не удалось проверить лимит ИИ"

_RESERVE_SCRIPT = """
local requests = tonumber(redis.call('HGET', KEYS[1], 'requests') or '0')
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens') or '0')
if requests >= tonumber(ARGV[1]) or tokens + tonumber(ARGV[3]) > tonumber(ARGV[2]) then
    return {0, requests, tokens}
end
requests = redis.call('HINCRBY', KEYS[1], 'requests', 1)
tokens = redis.call('HINCRBY', KEYS[1], 'tokens', ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return {1, requests, tokens}
"""


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
        self._reserve = client.register_script(_RESERVE_SCRIPT)
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
        """Дешёвая проверка до стрима; гонку закрывает `reserve_step`."""
        usage = await self.usage()
        if (
            usage.requests < settings.AI_DAILY_REQUEST_LIMIT
            and usage.tokens < settings.AI_DAILY_TOKEN_LIMIT
        ):
            return
        await self._reject(usage)

    async def reserve_step(self, estimate: int) -> int:
        """Атомарно зарезервировать токены шага и учесть обращение; вернуть резерв."""
        with _redis_guard():
            allowed, requests, tokens = await self._reserve(
                keys=[self._key()],
                args=[
                    settings.AI_DAILY_REQUEST_LIMIT,
                    settings.AI_DAILY_TOKEN_LIMIT,
                    estimate,
                    KEY_TTL_SECONDS,
                ],
            )
        self.last_usage = QuotaUsage(requests=requests, tokens=tokens)
        if not allowed:
            await self._reject(self.last_usage)
        await self._warn_if_near_limit(self.last_usage)
        return estimate

    async def settle_step(self, reserved: int, actual: int) -> None:
        """Пересчитать резерв шага по фактическому расходу."""
        delta = actual - reserved
        if delta == 0 or self.last_usage is None:
            return
        with _redis_guard():
            tokens = await self._client.hincrby(self._key(), _TOKENS, delta)
        self.last_usage = QuotaUsage(requests=self.last_usage.requests, tokens=tokens)
        await self._warn_if_near_limit(self.last_usage)

    async def _reject(self, usage: QuotaUsage) -> NoReturn:
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

    async def _warn_if_near_limit(self, usage: QuotaUsage) -> None:
        limit = settings.AI_DAILY_TOKEN_LIMIT
        if usage.tokens >= WARN_FRACTION * limit and await self._set_flag(
            _FLAG_WARNED_80,
        ):
            logger.warning(
                "ИИ: израсходовано 80%% дневного лимита токенов (%d/%d)",
                usage.tokens,
                limit,
            )

    async def _set_flag(self, flag: str) -> bool:
        """`True`, если флаг выставлен впервые; сбой Redis не пробрасывается."""
        try:
            return bool(await self._client.hsetnx(self._key(), flag, 1))
        except RedisError, OSError:
            logger.warning("ИИ: не удалось выставить флаг %s", flag, exc_info=True)
            return False
