from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import httpx


async def iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    """Отдать значение `data` каждого события `text/event-stream`."""
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if field == "data":
            data_lines.append(value.removeprefix(" "))
    if data_lines:
        yield "\n".join(data_lines)
