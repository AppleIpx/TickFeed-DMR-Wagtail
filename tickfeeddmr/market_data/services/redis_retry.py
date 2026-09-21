from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

if TYPE_CHECKING:
    import logging

REDIS_TRANSIENT_ERRORS = (RedisConnectionError, RedisTimeoutError)

REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS = 10

INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2


class RedisRetryLoop:
    """Держит attempt/backoff-состояние между итерациями внешнего `while True`.

    `reset()` — после успешного восстановления соединения (сбрасывает
    счётчик и backoff до начального). `sleep_after_failure()` — на
    `REDIS_TRANSIENT_ERRORS`: логирует WARNING и ждёт растущий backoff.
    """

    def __init__(self, *, logger: logging.Logger, label: str) -> None:
        self._logger = logger
        self._label = label
        self._attempt = 0
        self._backoff = INITIAL_BACKOFF_SECONDS

    def reset(self) -> None:
        self._attempt = 0
        self._backoff = INITIAL_BACKOFF_SECONDS

    async def sleep_after_failure(self, exc: Exception) -> None:
        self._attempt += 1
        self._logger.warning(
            f"{self._label}: разрыв соединения с Redis (попытка={self._attempt}), "
            f"переподключение через {self._backoff:.1f}с: {exc}",
        )
        await asyncio.sleep(self._backoff)
        self._backoff = min(self._backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
