import logging
import time
from typing import TYPE_CHECKING

from redis.exceptions import ResponseError

from tickfeeddmr.market_data.services.stream_settings import (
    validate_trade_stream_retention,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

validate_trade_stream_retention()

_MS_PER_SECOND = 1000


def _parse_stream_id(stream_id: str) -> tuple[int, int]:
    """`<ms>-<seq>` -> `(ms, seq)`; сравнимо кортежами."""
    ms, _, seq = stream_id.partition("-")
    return int(ms), int(seq or 0)


def stream_ceiling_minid(*, ceiling_seconds: int) -> str:
    """`MINID` потолка для `XADD` продюсера: записи старше него подрезаются."""
    return str(int(time.time() * _MS_PER_SECOND) - ceiling_seconds * _MS_PER_SECOND)


class TradeStreamTrimmer:
    """Помнит последнюю записанную в БД запись и периодически обрезает стрим."""

    def __init__(
        self,
        *,
        stream_key: str,
        gap_seconds: int,
        interval_seconds: int,
    ) -> None:
        self._stream_key = stream_key
        self._gap_ms = gap_seconds * _MS_PER_SECOND
        self._interval_seconds = interval_seconds
        self._last_written: tuple[int, int] | None = None
        self._last_trim_at = time.monotonic()

    def note_written(self, message_id: str | None) -> None:
        """Запомнить id последней записи пачки, успешно записанной в БД.

        `None` — пачка не записалась (или пустая): граница не двигается.
        Состояние живёт в процессе; после рестарта до первой успешной пачки
        обрезка не выполняется — это безопасно.
        """
        if message_id is None:
            return
        parsed = _parse_stream_id(message_id)
        if self._last_written is None or parsed > self._last_written:
            self._last_written = parsed

    async def maybe_trim(self, redis_client: Redis) -> None:
        """`XTRIM MINID` по более старой из границ, не чаще раза в интервал."""
        if self._last_written is None:
            return
        if time.monotonic() - self._last_trim_at < self._interval_seconds:
            return
        self._last_trim_at = time.monotonic()

        now_ms = int(time.time() * _MS_PER_SECOND)
        boundary_ms = min(self._last_written[0], now_ms - self._gap_ms)
        try:
            trimmed = await redis_client.xtrim(
                self._stream_key,
                minid=str(boundary_ms),
                approximate=True,
            )
        except ResponseError as exc:
            logger.warning(f"Не удалось обрезать стрим {self._stream_key}: {exc}")
            return
        if trimmed and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Стрим {self._stream_key} обрезан по MINID={boundary_ms}: "
                f"удалено {trimmed} записей",
            )
