import logging
import time
from collections.abc import AsyncGenerator, Hashable
from typing import TYPE_CHECKING, cast

from django.conf import settings
from redis.asyncio import Redis

from tickfeeddmr.market_data.services.redis_retry import (
    REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS,
    REDIS_TRANSIENT_ERRORS,
    RedisRetryLoop,
)
from tickfeeddmr.market_data.services.stream_selection import select_per_group
from tickfeeddmr.market_data.services.trade_stream import (
    MALFORMED_TRADE_EVENT_ERRORS,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.services.stream_reader.schemas import LiveStreamSpec

logger = logging.getLogger(__name__)

_MS_PER_SECOND = 1000
_EMPTY_STREAM_ID = "0-0"

type _XReadResponse = list[tuple[str, list[tuple[str, dict[str, str]]]]]


class Heartbeat:
    """Маркер «прошло heartbeat-время без событий»; контроллер шлёт `heartbeat`."""

    __slots__ = ()


HEARTBEAT = Heartbeat()


async def read_live_stream[T, G: Hashable](
    spec: LiveStreamSpec[T, G],
) -> AsyncGenerator[list[T] | Heartbeat]:
    """Бесконечный генератор пачек отобранных событий и heartbeat-маркеров.

    Завершается только отменой (уход клиента: `CancelledError`/`aclose()`) —
    `finally` закрывает клиент Redis. `CancelledError` намеренно не
    перехватывается.
    """
    window = settings.MARKET_DATA_SSE_WINDOW_SECONDS
    heartbeat = settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS
    read_count = settings.MARKET_DATA_SSE_READ_COUNT

    retry = RedisRetryLoop(logger=logger, label=spec.label)
    last_id: str | None = None
    buffer: list[T] = []
    started = time.monotonic()
    window_ends = started + window
    last_emit = started

    while True:
        client: Redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=window + REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS,
        )
        try:
            if last_id is None:
                last_id = await _current_tail_id(client, spec.stream_key)
            while True:
                block_ms = max(
                    int((window_ends - time.monotonic()) * _MS_PER_SECOND),
                    1,
                )
                response = await client.xread(
                    {spec.stream_key: last_id},
                    count=read_count,
                    block=block_ms,
                )
                retry.reset()
                for _stream_key, messages in cast("_XReadResponse", response or []):
                    for message_id, fields in messages:
                        # Пропущенное всё равно двигает курсор: иначе читали бы
                        # чужие тикеры заново на каждом проходе.
                        last_id = message_id
                        _collect(spec, buffer, message_id, fields)

                now = time.monotonic()
                if now >= window_ends:
                    window_ends = now + window
                    if buffer:
                        selected = select_per_group(
                            buffer,
                            group_key=spec.group_key,
                            rule=spec.rule,
                            order_key=spec.order_key,
                        )
                        buffer = []
                        last_emit = now
                        yield selected
                if time.monotonic() - last_emit >= heartbeat:
                    last_emit = time.monotonic()
                    yield HEARTBEAT
        except REDIS_TRANSIENT_ERRORS as exc:
            await retry.sleep_after_failure(exc)
        finally:
            await client.aclose()


async def _current_tail_id(client: Redis, stream_key: str) -> str:
    """Превратить «`$`» в конкретный id один раз.

    Повторный `$` в каждом `XREAD` терял бы записи, добавленные между
    вызовами: `$` означает «конец стрима на момент этого вызова».
    """
    entries = await client.xrevrange(stream_key, count=1)
    return str(entries[0][0]) if entries else _EMPTY_STREAM_ID


def _collect[T, G: Hashable](
    spec: LiveStreamSpec[T, G],
    buffer: list[T],
    message_id: str,
    fields: dict[str, str],
) -> None:
    if not spec.accept_raw(fields):
        return
    try:
        buffer.append(spec.decode(fields))
    except MALFORMED_TRADE_EVENT_ERRORS:
        logger.exception(f"Битая запись сделки в стриме, пропускаем id={message_id}")
