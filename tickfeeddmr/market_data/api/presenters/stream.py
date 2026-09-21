from contextlib import aclosing
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from dmr.streaming.sse import SSEvent

from tickfeeddmr.market_data.api.schemas.common import HeartbeatOut, StreamWarningOut
from tickfeeddmr.market_data.services.stream_reader import Heartbeat

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable

    import msgspec

    from tickfeeddmr.market_data.services.queries.types import StreamTargets


def stream_warning(
    targets: StreamTargets,
    *,
    list_url: str,
    reason: str,
) -> StreamWarningOut | None:
    """Предупреждение о ненайденных тикерах — первым событием потока.

    `None`, если все запрошенные тикеры найдены (или фильтра не было).
    """
    if not targets.unknown:
        return None
    found = ", ".join(targets.symbols_by_stream_key.values())
    return StreamWarningOut(
        unknown=targets.unknown,
        detail=(
            f"{reason}: {', '.join(targets.unknown)}. "
            f"Данные по ним приходить не будут. Поток по остальным тикерам "
            f"({found}) продолжается. Актуальный список — GET {list_url}"
        ),
    )


async def sse_events[T](
    batches: AsyncGenerator[list[T] | Heartbeat],
    *,
    to_trade_event: Callable[[T], msgspec.Struct],
    warning: StreamWarningOut | None,
) -> AsyncIterator[SSEvent[Any]]:
    """Превратить пачки читателя стрима в SSE-события.

    Порядок: `warning` (если есть) -> `trade` на каждую отобранную сделку ->
    `heartbeat` в тишине. `SSEvent.id` не выставляется: докачки по
    `Last-Event-ID` нет, фронт при реконнекте перезагружает состояние сам.

    `aclosing` — обязательный: при уходе клиента DMR закрывает этот
    генератор, но не вложенный `batches`, и без явного закрытия клиент Redis
    жил бы до сборщика мусора.
    """
    async with aclosing(batches):
        if warning is not None:
            yield SSEvent(warning, event="warning")
        async for batch in batches:
            if isinstance(batch, Heartbeat):
                yield SSEvent(
                    HeartbeatOut(timestamp=datetime.now(UTC)),
                    event="heartbeat",
                )
                continue
            for item in batch:
                yield SSEvent(to_trade_event(item), event="trade")
