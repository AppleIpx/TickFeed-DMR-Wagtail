from typing import TYPE_CHECKING

from redis.asyncio import Redis

from tickfeeddmr.market_data.services.moex_trade_stream.serialization import (
    serialize_moex_trade,
)
from tickfeeddmr.market_data.services.trade_stream_retention import (
    stream_ceiling_minid,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.moex.types import MoexTradeRow


class MoexTradeStreamPublisher:
    """Пишет отобранные сделки акций в Redis Stream с ретеншном на каждом `XADD`.

    Владеет собственным `Redis`-клиентом (как `redis_lock`): открывается на
    прогон поллера, закрывается через `aclose()` в `finally` рядом с
    `provider.aclose()`.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        stream_key: str,
        retention_seconds: int,
    ) -> None:
        self._client: Redis = Redis.from_url(redis_url, decode_responses=True)
        self._stream_key = stream_key
        self._retention_seconds = retention_seconds

    async def publish(self, secid: str, rows: list[MoexTradeRow]) -> int:
        """Записать `rows` пачкой, вернуть число записанных сделок."""
        if not rows:
            return 0
        minid = stream_ceiling_minid(ceiling_seconds=self._retention_seconds)
        async with self._client.pipeline(transaction=False) as pipe:
            for row in rows:
                pipe.xadd(
                    self._stream_key,
                    serialize_moex_trade(secid, row),
                    minid=minid,
                    approximate=True,
                )
            await pipe.execute()
        return len(rows)

    async def aclose(self) -> None:
        await self._client.aclose()
