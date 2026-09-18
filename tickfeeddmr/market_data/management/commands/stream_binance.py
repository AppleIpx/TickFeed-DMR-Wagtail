import asyncio
import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from redis.asyncio import Redis

from tickfeeddmr.market_data.models import CryptoAsset
from tickfeeddmr.market_data.providers.binance import EXCHANGE, BinanceProvider
from tickfeeddmr.market_data.services.redis_retry import (
    REDIS_TRANSIENT_ERRORS,
    RedisRetryLoop,
)
from tickfeeddmr.market_data.services.trade_stream import serialize_trade_event

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Стримит сделки Binance активных CryptoAsset в Redis Stream (один сокет)."

    def handle(self, *args: Any, **options: Any) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        trading_pairs = await self._active_trading_pairs()
        if not trading_pairs:
            logger.warning(
                f"Нет активных CryptoAsset для exchange={EXCHANGE}, стримить нечего",
            )
            return

        retry = RedisRetryLoop(logger=logger, label="stream_binance")
        while True:
            provider = BinanceProvider(
                rest_base_url=settings.BINANCE_REST_BASE_URL,
                ws_base_url=settings.BINANCE_WS_BASE_URL,
            )
            redis_client: Redis = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            try:
                async for event in provider.stream(trading_pairs):
                    await redis_client.xadd(
                        settings.MARKET_DATA_TRADE_STREAM_KEY,
                        serialize_trade_event(event),
                    )
                    retry.reset()
            except REDIS_TRANSIENT_ERRORS as exc:
                await retry.sleep_after_failure(exc)
            finally:
                await redis_client.aclose()
                await provider.aclose()

    @staticmethod
    async def _active_trading_pairs() -> list[str]:
        return [
            pair
            async for pair in CryptoAsset.objects.filter(
                exchange=EXCHANGE,
                is_active=True,
            ).values_list("trading_pair", flat=True)
        ]
