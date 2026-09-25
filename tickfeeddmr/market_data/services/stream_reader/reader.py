import asyncio
import time
from collections.abc import AsyncGenerator, Hashable
from typing import TYPE_CHECKING

from django.conf import settings

from tickfeeddmr.market_data.services.stream_reader.hub import (
    register_subscriber,
    unregister_subscriber,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.services.stream_reader.schemas import LiveStreamSpec


class Heartbeat:
    """Маркер «прошло heartbeat-время без событий»; контроллер шлёт `heartbeat`."""

    __slots__ = ()


HEARTBEAT = Heartbeat()


async def subscribe[T, G: Hashable](
    spec: LiveStreamSpec[T, G],
    wanted: frozenset[G],
) -> AsyncGenerator[list[T] | Heartbeat]:
    """Один подписчик общего хаба `spec.stream_key` — одна SSE-сессия.

    Хаб — общий Redis-ридер на `stream_key` на процесс,
    заводится лениво первым подписчиком и останавливается, когда уходит
    последний; этот генератор лишь регистрируется в нём и ждёт свою пачку.

    """
    heartbeat_interval = settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS
    hub, subscriber = await register_subscriber(spec, wanted)
    try:
        deadline = time.monotonic() + heartbeat_interval
        while True:
            remaining = max(deadline - time.monotonic(), 0.0)
            try:
                async with asyncio.timeout(remaining):
                    batch = await subscriber.wait()
            except TimeoutError:
                batch = None
            if subscriber.closed:
                return
            deadline = time.monotonic() + heartbeat_interval
            yield batch if batch is not None else HEARTBEAT
    finally:
        await unregister_subscriber(hub, subscriber)
