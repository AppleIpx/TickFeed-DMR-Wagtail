import asyncio
import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.management.base import BaseCommand
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from tickfeeddmr.market_data.providers.binance import EXCHANGE
from tickfeeddmr.market_data.services.ingest import CryptoTradeIngestService
from tickfeeddmr.market_data.services.redis_retry import (
    REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS,
    REDIS_TRANSIENT_ERRORS,
    RedisRetryLoop,
)
from tickfeeddmr.market_data.services.trade_stream import (
    MALFORMED_TRADE_EVENT_ERRORS,
    deserialize_trade_event,
)
from tickfeeddmr.market_data.services.trade_stream_retention import TradeStreamTrimmer

if TYPE_CHECKING:
    from tickfeeddmr.market_data.providers.base import TradeEvent

logger = logging.getLogger(__name__)

GROUP_ALREADY_EXISTS = "BUSYGROUP"
PENDING_ENTRIES_START_ID = "0"
NEW_ENTRIES_ID = ">"


class Command(BaseCommand):
    help = "Читает Redis Stream сделок (consumer group) и пишет CryptoPriceSnapshot."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Состояние обрезки живёт весь процесс и переживает переподключения к
        # Redis: id записей сквозные по стриму, а не по соединению.
        self._trimmer = TradeStreamTrimmer(
            stream_key=settings.MARKET_DATA_TRADE_STREAM_KEY,
            gap_seconds=settings.MARKET_DATA_TRADE_TRIM_GAP_SECONDS,
            interval_seconds=settings.MARKET_DATA_TRADE_TRIM_INTERVAL_SECONDS,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        ingest = CryptoTradeIngestService(exchange=EXCHANGE)
        retry = RedisRetryLoop(logger=logger, label="consume_market_data_stream")
        while True:
            redis_client: Redis = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=(
                    settings.MARKET_DATA_TRADE_READ_BLOCK_MS / 1000
                    + REDIS_SOCKET_TIMEOUT_MARGIN_SECONDS
                ),
            )
            try:
                await self._ensure_group(redis_client)
                await self._recover_pending(redis_client, ingest)
                retry.reset()
                while True:
                    response = await redis_client.xreadgroup(
                        groupname=settings.MARKET_DATA_TRADE_CONSUMER_GROUP,
                        consumername=settings.MARKET_DATA_TRADE_CONSUMER_NAME,
                        streams={
                            settings.MARKET_DATA_TRADE_STREAM_KEY: NEW_ENTRIES_ID,
                        },
                        count=settings.MARKET_DATA_TRADE_READ_COUNT,
                        block=settings.MARKET_DATA_TRADE_READ_BLOCK_MS,
                    )
                    if not _has_messages(response):
                        continue
                    written_id = await self._process_batch(
                        redis_client,
                        ingest,
                        response,
                    )
                    self._trimmer.note_written(written_id)
                    await self._trimmer.maybe_trim(redis_client)
            except REDIS_TRANSIENT_ERRORS as exc:
                await retry.sleep_after_failure(exc)
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
            written_id = await self._process_batch(redis_client, ingest, response)
            self._trimmer.note_written(written_id)

    async def _process_batch(
        self,
        redis_client: Redis,
        ingest: CryptoTradeIngestService,
        response: list[tuple[str, list[tuple[str, dict[str, str]]]]],
    ) -> str | None:
        """Записать пачку в БД и подтвердить её (`XACK`).

        Возвращает id последней записи пачки, если пачка записана без
        исключения, иначе `None` — граница обрезки стрима
        (`TradeStreamTrimmer`) тогда не двигается. Данные неудавшейся пачки
        всё равно уже подтверждены и потеряны, но лишнего мы не подрезаем.
        """
        last_written_id: str | None = None
        for _stream_key, messages in response:
            message_ids = [message_id for message_id, _fields in messages]
            events = _decode_messages(messages)

            try:
                # Сознательно широкий catch — см. докстринг модуля: ack всё равно
                # произойдёт ниже, чтобы одна плохая запись не блокировала стрим.
                written = await ingest.write_snapshots(events)
            except Exception:
                logger.exception("Не удалось записать пачку CryptoPriceSnapshot")
            else:
                if message_ids:
                    last_written_id = message_ids[-1]
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
        return last_written_id


def _decode_messages(messages: list[tuple[str, dict[str, str]]]) -> list[TradeEvent]:
    """Разобрать записи пачки в `TradeEvent`, пропуская обрезанные и битые.

    Запись из PEL, которую уже удалила обрезка стрима, redis-py отдаёт как
    `(id, {})`. Это не «битая» запись, а потеря данных ретеншном — логируем
    отдельно, одним WARNING на пачку, чтобы причина не терялась в
    «Битая запись».
    """
    events: list[TradeEvent] = []
    truncated = 0
    for message_id, fields in messages:
        if not fields:
            truncated += 1
            continue
        try:
            events.append(deserialize_trade_event(fields))
        except MALFORMED_TRADE_EVENT_ERRORS:
            logger.exception(
                f"Битая запись сделки в стриме, пропускаем id={message_id}",
            )
    if truncated:
        logger.warning(
            f"{truncated} записей стрима обрезаны ретеншном до обработки "
            f"(PEL указывает на удалённые записи), сделки потеряны",
        )
    return events


def _has_messages(response: list[tuple[str, list[tuple[str, dict[str, str]]]]]) -> bool:
    """`XREADGROUP` возвращает `[]` либо `[(stream_key, [])]` — оба значат "пусто"."""
    return any(messages for _stream_key, messages in response)


def _count_messages(
    response: list[tuple[str, list[tuple[str, dict[str, str]]]]],
) -> int:
    return sum(len(messages) for _stream_key, messages in response)
