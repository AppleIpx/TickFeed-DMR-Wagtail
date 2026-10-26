import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def next_before[T](stream: AsyncIterator[T], deadline: float) -> T | None:
    """Следующий элемент потока или `None` в конце; ожидание ограничено дедлайном."""
    async with asyncio.timeout_at(deadline):
        return await anext(stream, None)
