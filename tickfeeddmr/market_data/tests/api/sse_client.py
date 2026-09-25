from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from django.test import AsyncRequestFactory
    from dmr.streaming.stream import StreamingResponse
    from dmr.test import DMRAsyncClient

_DEFAULT_TIMEOUT = 5.0


async def open_sse_stream(
    client: DMRAsyncClient,
    rf: AsyncRequestFactory,
    path: str,
) -> StreamingResponse:
    """Открыть SSE-ручку, вернуть сырой `StreamingResponse` (200 гарантирован)."""
    request = rf.get(path)
    handler = client.handler
    if handler._middleware_chain is None:  # noqa: SLF001
        handler.load_middleware(is_async=True)
    return await handler.get_response_async(request)


def parse_sse_chunk(chunk: bytes) -> tuple[str | None, dict[str, Any]]:
    """Разобрать один SSE-блок."""
    event: str | None = None
    data: str | None = None
    for line in chunk.decode("utf-8").split("\r\n"):
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data = line.removeprefix("data: ")
    if data is None:
        msg = f"SSE chunk without a data line: {chunk!r}"
        raise AssertionError(msg)
    return event, json.loads(data)


async def next_non_heartbeat_chunk(
    agen: AsyncIterator[bytes],
) -> tuple[str | None, dict[str, Any]]:
    """Пропустить `heartbeat`-и, дождаться первого события другого рода."""
    async with asyncio.timeout(_DEFAULT_TIMEOUT):
        while True:
            kind, body = parse_sse_chunk(await agen.__anext__())
            if kind != "heartbeat":
                return kind, body


async def collect_sse_events(
    response: StreamingResponse,
    count: int,
) -> list[tuple[str | None, dict[str, Any]]]:
    """Прочитать ровно `count` событий (общий бюджет — `_DEFAULT_TIMEOUT`) и
    закрыть генератор (`aclose()`).
    """
    agen = response.__aiter__()
    events: list[tuple[str | None, dict[str, Any]]] = []
    try:
        async with asyncio.timeout(_DEFAULT_TIMEOUT):
            for _ in range(count):
                chunk = await agen.__anext__()
                events.append(parse_sse_chunk(chunk))
    finally:
        await agen.aclose()
    return events
