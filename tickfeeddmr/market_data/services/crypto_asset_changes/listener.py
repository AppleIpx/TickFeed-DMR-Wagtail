import logging
from typing import TYPE_CHECKING, cast

import msgspec

from tickfeeddmr.market_data.services.crypto_asset_changes.schemas import (
    CryptoAssetChange,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.serialization import (
    MALFORMED_ASSET_CHANGE_ERRORS,
    deserialize_crypto_asset_change,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.settings import (
    validate_crypto_asset_change_settings,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

validate_crypto_asset_change_settings()

_EMPTY_STREAM_ID = "0-0"

type _XReadResponse = list[tuple[str, list[tuple[str, dict[str, str]]]]]


class AssetChangeBatch(msgspec.Struct, frozen=True):
    """Пачка событий одного `XREAD`: id последней записи и разобранные события.

    Битые записи в `changes` не попадают, но `last_id` их учитывает — сверку
    пачка запускает в любом случае.
    """

    last_id: str
    changes: tuple[CryptoAssetChange, ...]


async def resolve_start_id(redis_client: Redis, stream_key: str) -> str:
    """Id последней записи стрима, `"0-0"` для пустого/несуществующего.

    Берётся ДО чтения активных пар из БД: событие с id не больше этого
    опубликовано после коммита, значит его изменение уже видно в БД. `$`
    в `XREAD` не годится — между вызовами терялись бы записи.
    """
    entries = cast(
        "list[tuple[str, dict[str, str]]]",
        await redis_client.xrevrange(stream_key, count=1),
    )
    if not entries:
        return _EMPTY_STREAM_ID
    return entries[0][0]


async def read_asset_changes(
    redis_client: Redis,
    *,
    stream_key: str,
    last_id: str,
    count: int,
    block_ms: int,
) -> AssetChangeBatch | None:
    """`XREAD BLOCK` после `last_id`; `None`, если за `block_ms` ничего не пришло."""
    response = cast(
        "_XReadResponse",
        await redis_client.xread({stream_key: last_id}, count=count, block=block_ms)
        or [],
    )
    messages = [message for _key, entries in response for message in entries]
    if not messages:
        return None

    changes: list[CryptoAssetChange] = []
    for message_id, fields in messages:
        try:
            changes.append(deserialize_crypto_asset_change(fields))
        except MALFORMED_ASSET_CHANGE_ERRORS:
            logger.exception(
                f"Битая запись в стриме изменений CryptoAsset, id={message_id}",
            )
    return AssetChangeBatch(last_id=messages[-1][0], changes=tuple(changes))
