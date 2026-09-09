import asyncio
import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.management.base import BaseCommand
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from tickfeeddmr.market_data.providers.binance import EXCHANGE
from tickfeeddmr.market_data.services.ingest import CryptoTradeIngestService
from tickfeeddmr.market_data.services.trade_stream import (
    MALFORMED_TRADE_EVENT_ERRORS,
    deserialize_trade_event,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.base import TradeEvent

logger = logging.getLogger(__name__)

GROUP_ALREADY_EXISTS = "BUSYGROUP"
PENDING_ENTRIES_START_ID = "0"
NEW_ENTRIES_ID = ">"
# redis-py по умолчанию ставит клиентский socket_timeout=5с (DEFAULT_SOCKET_TIMEOUT
# в redis/_defaults.py) — ровно столько же, сколько MARKET_DATA_TRADE_READ_BLOCK_MS
# по умолчанию просит подержать XREADGROUP открытым на сервере. Это гонка двух
# одинаковых таймеров: если клиентский сокет-таймаут срабатывает хоть на миллисекунду
# раньше серверного BLOCK, redis-py кидает жёсткий TimeoutError вместо тихого пустого
# ответа (graceful-путь есть только когда timeout передан на конкретный вызов, а не
# через socket_timeout соединения). Держим клиентский таймаут с большим запасом над
# BLOCK, чтобы сервер всегда успевал ответить первым.
REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS = 10


class Command(BaseCommand):
    help = "Читает Redis Stream сделок (consumer group) и пишет CryptoPriceSnapshot."

    def handle(self, *args: Any, **options: Any) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        redis_client: Redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=(
                settings.MARKET_DATA_TRADE_READ_BLOCK_MS / 1000
                + REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS
            ),
        )
        ingest = CryptoTradeIngestService(exchange=EXCHANGE)
        try:
            await self._ensure_group(redis_client)
            await self._recover_pending(redis_client, ingest)
            while True:
                response = await redis_client.xreadgroup(
                    groupname=settings.MARKET_DATA_TRADE_CONSUMER_GROUP,
                    consumername=settings.MARKET_DATA_TRADE_CONSUMER_NAME,
                    streams={settings.MARKET_DATA_TRADE_STREAM_KEY: NEW_ENTRIES_ID},
                    count=settings.MARKET_DATA_TRADE_READ_COUNT,
                    block=settings.MARKET_DATA_TRADE_READ_BLOCK_MS,
                )
                if not _has_messages(response):
                    continue
                await self._process_batch(redis_client, ingest, response)
        finally:
            await redis_client.aclose()

    async def _ensure_group(self, redis_client: Redis) -> None:
        try:
            await redis_client.xgroup_create(
                settings.MARKET_DATA_TRADE_STREAM_KEY,
                settings.MARKET_DATA_TRADE_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if GROUP_ALREADY_EXISTS not in str(exc):
                raise
            logger.info(
                f"Группа консьюмеров {settings.MARKET_DATA_TRADE_CONSUMER_GROUP} "
                f"уже существует на стриме {settings.MARKET_DATA_TRADE_STREAM_KEY}",
            )

    async def _recover_pending(
        self,
        redis_client: Redis,
        ingest: CryptoTradeIngestService,
    ) -> None:
        """Дочитывает и обрабатывает PEL этого консьюмера с прошлого запуска.

        Если процесс упал после `xreadgroup`, но до `xack` в конце пачки,
        эти сообщения остаются в PEL и никогда не попадут в чтение через
        `>` (оно отдаёт только новые записи). Без этого шага backlog не
        переживает падение ровно там, где мы обещали это Redis Streams, а
        не Pub/Sub.
        """
        while True:
            response = await redis_client.xreadgroup(
                groupname=settings.MARKET_DATA_TRADE_CONSUMER_GROUP,
                consumername=settings.MARKET_DATA_TRADE_CONSUMER_NAME,
                streams={
                    settings.MARKET_DATA_TRADE_STREAM_KEY: PENDING_ENTRIES_START_ID,
                },
                count=settings.MARKET_DATA_TRADE_READ_COUNT,
            )
            if not _has_messages(response):
                return
            logger.info(
                f"Восстанавливаем {_count_messages(response)} необработанных "
                f"сделок с прошлого запуска",
            )
            await self._process_batch(redis_client, ingest, response)

    async def _process_batch(
        self,
        redis_client: Redis,
        ingest: CryptoTradeIngestService,
        response: list[tuple[str, list[tuple[str, dict[str, str]]]]],
    ) -> None:
        for _stream_key, messages in response:
            events: list[TradeEvent] = []
            message_ids = [message_id for message_id, _fields in messages]

            for message_id, fields in messages:
                try:
                    events.append(deserialize_trade_event(fields))
                except MALFORMED_TRADE_EVENT_ERRORS:
                    logger.exception(
                        f"Битая запись сделки в стриме, пропускаем id={message_id}",
                    )

            try:
                # Сознательно широкий catch — см. докстринг модуля: ack всё равно
                # произойдёт ниже, чтобы одна плохая запись не блокировала стрим.
                written = await ingest.write_snapshots(events)
            except Exception:
                logger.exception("Не удалось записать пачку CryptoPriceSnapshot")
            else:
                # Хот-путь: вызывается на каждую обработанную пачку. f-строка
                # собирается всегда, даже когда DEBUG не пишется (root на INFO) —
                # явная проверка нужна, см. конвенцию логирования в CLAUDE.md.
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Записано {written} строк CryptoPriceSnapshot "
                        f"из {len(messages)} сообщений",
                    )

            if message_ids:
                await redis_client.xack(
                    settings.MARKET_DATA_TRADE_STREAM_KEY,
                    settings.MARKET_DATA_TRADE_CONSUMER_GROUP,
                    *message_ids,
                )


def _has_messages(response: list[tuple[str, list[tuple[str, dict[str, str]]]]]) -> bool:
    """`XREADGROUP` возвращает `[]` либо `[(stream_key, [])]` — оба значат "пусто"."""
    return any(messages for _stream_key, messages in response)


def _count_messages(
    response: list[tuple[str, list[tuple[str, dict[str, str]]]]],
) -> int:
    return sum(len(messages) for _stream_key, messages in response)
