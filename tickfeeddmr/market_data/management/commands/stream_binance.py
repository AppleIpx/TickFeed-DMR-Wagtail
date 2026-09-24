import asyncio
import logging
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import DatabaseError, close_old_connections
from redis.asyncio import Redis

from tickfeeddmr.market_data.models import CryptoAsset
from tickfeeddmr.market_data.providers.binance import EXCHANGE, BinanceProvider
from tickfeeddmr.market_data.services.crypto_asset_changes.listener import (
    read_asset_changes,
    resolve_start_id,
)
from tickfeeddmr.market_data.services.redis_retry import (
    BACKOFF_MULTIPLIER,
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS,
    REDIS_TRANSIENT_ERRORS,
    RedisRetryLoop,
)
from tickfeeddmr.market_data.services.trade_stream import serialize_trade_event
from tickfeeddmr.market_data.services.trade_stream_retention import (
    stream_ceiling_minid,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.binance.websocket import (
        BinanceTradeStreamConsumer,
    )

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Стримит сделки Binance активных CryptoAsset в Redis Stream (один сокет); "
        "набор пар меняется на лету по событиям изменения CryptoAsset."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        provider = BinanceProvider(
            rest_base_url=settings.BINANCE_REST_BASE_URL,
            ws_base_url=settings.BINANCE_WS_BASE_URL,
        )
        consumer = provider.trade_stream()
        try:
            start_id = await self._resolve_changes_start_id()
            trading_pairs = await _active_trading_pairs()
            logger.info(
                f"Стартовый набор пар Binance: {len(trading_pairs)}, события "
                f"изменений CryptoAsset читаются после id={start_id}",
            )
            await consumer.update_pairs(trading_pairs)
            async with asyncio.TaskGroup() as task_group:
                task_group.create_task(self._pump_trades(consumer))
                task_group.create_task(
                    self._watch_asset_changes(consumer, start_id),
                )
        finally:
            await provider.aclose()

    async def _pump_trades(self, consumer: BinanceTradeStreamConsumer) -> None:
        """Сокет Binance -> `XADD` в стрим сделок."""
        retry = RedisRetryLoop(logger=logger, label="stream_binance")
        while True:
            redis_client: Redis = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            events = consumer.stream()
            try:
                async for event in events:
                    await redis_client.xadd(
                        settings.MARKET_DATA_TRADE_STREAM_KEY,
                        serialize_trade_event(event),
                        minid=stream_ceiling_minid(
                            ceiling_seconds=(
                                settings.MARKET_DATA_TRADE_STREAM_CEILING_SECONDS
                            ),
                        ),
                        approximate=True,
                    )
                    retry.reset()
            except REDIS_TRANSIENT_ERRORS as exc:
                await retry.sleep_after_failure(exc)
            finally:
                await events.aclose()
                await redis_client.aclose()

    async def _watch_asset_changes(
        self,
        consumer: BinanceTradeStreamConsumer,
        start_id: str,
    ) -> None:
        """`XREAD BLOCK` стрима изменений `CryptoAsset` -> сверка подписок с БД.

        Пачка событий схлопывается в одну сверку; `last_id` сдвигается только
        после неё. После восстановления соединения с Redis — одна сверка
        даже без событий: публикация, пришедшаяся на недоступный Redis,
        потеряна, и другого способа её заметить нет.
        """
        retry = RedisRetryLoop(logger=logger, label="stream_binance.asset_changes")
        last_id = start_id
        recovering = False
        while True:
            redis_client = self._changes_redis_client()
            try:
                while True:
                    batch = await read_asset_changes(
                        redis_client,
                        stream_key=settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_STREAM_KEY,
                        last_id=last_id,
                        count=settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_COUNT,
                        block_ms=settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_BLOCK_MS,
                    )
                    retry.reset()
                    if batch is None and not recovering:
                        continue
                    if batch is None:
                        reason = "восстановление соединения с Redis"
                    else:
                        for change in batch.changes:
                            logger.info(
                                f"Получено событие изменения CryptoAsset: "
                                f"{change.trading_pair} {change.kind} "
                                f"(asset_id={change.asset_id}, "
                                f"биржа={change.exchange})",
                            )
                        reason = f"событий изменения CryptoAsset: {len(batch.changes)}"
                    await self._reconcile(consumer, reason=reason)
                    recovering = False
                    if batch is not None:
                        last_id = batch.last_id
            except REDIS_TRANSIENT_ERRORS as exc:
                recovering = True
                await retry.sleep_after_failure(exc)
            finally:
                await redis_client.aclose()

    async def _reconcile(
        self,
        consumer: BinanceTradeStreamConsumer,
        *,
        reason: str,
    ) -> None:
        """Перечитать активные пары из БД и довести до них подписки сокета."""
        backoff = INITIAL_BACKOFF_SECONDS
        while True:
            try:
                trading_pairs = await _active_trading_pairs()
                break
            except DatabaseError as exc:
                logger.warning(
                    f"Сверка подписок Binance ({reason}): ошибка БД, повтор "
                    f"через {backoff:.1f}с: {exc}",
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
        logger.info(
            f"Сверка подписок Binance ({reason}): активных пар {len(trading_pairs)}",
        )
        await consumer.update_pairs(trading_pairs)

    async def _resolve_changes_start_id(self) -> str:
        retry = RedisRetryLoop(logger=logger, label="stream_binance.asset_changes")
        while True:
            redis_client = self._changes_redis_client()
            try:
                return await resolve_start_id(
                    redis_client,
                    settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_STREAM_KEY,
                )
            except REDIS_TRANSIENT_ERRORS as exc:
                await retry.sleep_after_failure(exc)
            finally:
                await redis_client.aclose()

    @staticmethod
    def _changes_redis_client() -> Redis:
        return Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=(
                settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_BLOCK_MS / 1000
                + REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS
            ),
        )


async def _active_trading_pairs() -> list[str]:
    await sync_to_async(close_old_connections)()
    return [
        pair
        async for pair in CryptoAsset.objects.filter(
            exchange=EXCHANGE,
            is_active=True,
        ).values_list("trading_pair", flat=True)
    ]
