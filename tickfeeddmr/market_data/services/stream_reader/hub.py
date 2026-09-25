import asyncio
import logging
import time
from collections.abc import Hashable
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from redis.asyncio import Redis

from tickfeeddmr.market_data.services.redis_retry import (
    REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS,
    REDIS_TRANSIENT_ERRORS,
    RedisRetryLoop,
)
from tickfeeddmr.market_data.services.trade_stream import (
    MALFORMED_TRADE_EVENT_ERRORS,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.services.stream_reader.schemas import LiveStreamSpec

logger = logging.getLogger(__name__)

_MS_PER_SECOND = 1000
_EMPTY_STREAM_ID = "0-0"

type _XReadResponse = list[tuple[str, list[tuple[str, dict[str, str]]]]]

_hubs: dict[str, _Hub[Any, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


class _Subscriber[T, G: Hashable]:
    """Один подписчик хаба — ячейка глубины 1 с drop-oldest."""

    def __init__(self, wanted: frozenset[G]) -> None:
        self.wanted = wanted
        self.closed = False
        self._pending: list[T] | None = None
        self._event = asyncio.Event()

    def deliver(self, batch: list[T]) -> None:
        """Заменить непрочитанную пачку новой — не поставить в очередь."""
        self._pending = batch
        self._event.set()

    def close(self) -> None:
        """Хаб завершился нештатно — разбудить подписчика, чтобы он вышел."""
        self.closed = True
        self._event.set()

    async def wait(self) -> list[T] | None:
        """Ждать следующую пачку."""
        await self._event.wait()
        self._event.clear()
        pending, self._pending = self._pending, None
        return pending


class _Hub[T, G: Hashable]:
    """Общий ридер `stream_key` — один Redis-клиент на процесс на все подписки."""

    def __init__(self, spec: LiveStreamSpec[T, G]) -> None:
        self._spec = spec
        self.stream_key = spec.stream_key
        self._active_groups: dict[G, int] = {}
        self._buffer: dict[G, list[T]] = {}
        self._subscribers: set[_Subscriber[T, G]] = set()
        self._task: asyncio.Task[None] | None = None

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def start(self) -> None:
        self._task = asyncio.ensure_future(self._run())

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    def add_subscriber(self, wanted: frozenset[G]) -> _Subscriber[T, G]:
        subscriber = _Subscriber[T, G](wanted)
        self._subscribers.add(subscriber)
        for group in wanted:
            self._active_groups[group] = self._active_groups.get(group, 0) + 1
        return subscriber

    def remove_subscriber(self, subscriber: _Subscriber[T, G]) -> None:
        self._subscribers.discard(subscriber)
        for group in subscriber.wanted:
            remaining = self._active_groups.get(group, 0) - 1
            if remaining <= 0:
                self._active_groups.pop(group, None)
            else:
                self._active_groups[group] = remaining

    async def _run(self) -> None:
        """Читать стрим, пока не отменят или не откажет неустранимо."""
        window = settings.MARKET_DATA_SSE_WINDOW_SECONDS
        read_count = settings.MARKET_DATA_SSE_READ_COUNT
        retry = RedisRetryLoop(logger=logger, label=self._spec.label)
        last_id: str | None = None
        window_ends = time.monotonic() + window
        try:
            while True:
                client: Redis = Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=window + REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS,
                )
                try:
                    if last_id is None:
                        last_id = await _current_tail_id(client, self.stream_key)
                    while True:
                        block_ms = max(
                            int((window_ends - time.monotonic()) * _MS_PER_SECOND),
                            1,
                        )
                        response = await client.xread(
                            {self.stream_key: last_id},
                            count=read_count,
                            block=block_ms,
                        )
                        retry.reset()
                        for _stream_key, messages in cast(
                            "_XReadResponse",
                            response or [],
                        ):
                            for message_id, fields in messages:
                                last_id = message_id
                                self._collect(message_id, fields)

                        now = time.monotonic()
                        if now >= window_ends:
                            window_ends = now + window
                            self._flush_window()
                except REDIS_TRANSIENT_ERRORS as exc:
                    await retry.sleep_after_failure(exc)
                finally:
                    await client.aclose()
        except Exception:
            logger.exception(f"{self._spec.label}: хаб остановлен нештатной ошибкой")
        finally:
            self._close_all_subscribers()

    def _collect(self, message_id: str, fields: dict[str, str]) -> None:
        group = self._spec.raw_group_key(fields)
        if group is None or self._active_groups.get(group, 0) <= 0:
            return
        try:
            item = self._spec.decode(fields)
        except MALFORMED_TRADE_EVENT_ERRORS:
            logger.exception(
                f"Битая запись сделки в стриме, пропускаем id={message_id}",
            )
            return
        self._buffer.setdefault(group, []).append(item)

    def _flush_window(self) -> None:
        """Отобрать по группе один раз, раздать по подписчикам отдельно."""
        if not self._buffer:
            return
        per_group_selected = {
            group: self._spec.rule(items) for group, items in self._buffer.items()
        }
        self._buffer.clear()
        for subscriber in self._subscribers:
            relevant = [
                item
                for group in subscriber.wanted
                for item in per_group_selected.get(group, ())
            ]
            if relevant:
                relevant.sort(key=self._spec.order_key)
                subscriber.deliver(relevant)

    def _close_all_subscribers(self) -> None:
        for subscriber in self._subscribers:
            subscriber.close()


async def _current_tail_id(client: Redis, stream_key: str) -> str:
    """Превратить «`$`» в конкретный id один раз, при старте хаба.

    Повторный `$` на каждый `XREAD` терял бы записи, добавленные между
    вызовами: `$` означает «конец стрима на момент этого вызова». Подписчик,
    присоединившийся к уже запущенному хабу, курсор не трогает — он просто
    начинает получать то, что попадёт в буфер с этого момента
    """
    entries = await client.xrevrange(stream_key, count=1)
    return str(entries[0][0]) if entries else _EMPTY_STREAM_ID


async def register_subscriber[T, G: Hashable](
    spec: LiveStreamSpec[T, G],
    wanted: frozenset[G],
) -> tuple[_Hub[T, G], _Subscriber[T, G]]:
    """Подписаться на хаб `spec.stream_key`, создав его при необходимости."""
    lock = _locks.setdefault(spec.stream_key, asyncio.Lock())
    async with lock:
        hub = _hubs.get(spec.stream_key)
        if hub is None:
            hub = _Hub(spec)
            hub.start()
            _hubs[spec.stream_key] = hub
        subscriber = hub.add_subscriber(wanted)
    return cast("_Hub[T, G]", hub), subscriber


async def unregister_subscriber[T, G: Hashable](
    hub: _Hub[T, G],
    subscriber: _Subscriber[T, G],
) -> None:
    """Отписаться; хаб без подписчиков останавливается и уходит из реестра."""
    lock = _locks[hub.stream_key]
    async with lock:
        hub.remove_subscriber(subscriber)
        if hub.subscriber_count == 0:
            del _hubs[hub.stream_key]
            await hub.stop()
