import logging
from typing import TYPE_CHECKING

import redis
from django.conf import settings
from redis.exceptions import RedisError

from tickfeeddmr.market_data.services.crypto_asset_changes.serialization import (
    serialize_crypto_asset_change,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.settings import (
    validate_crypto_asset_change_settings,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.services.crypto_asset_changes.schemas import (
        CryptoAssetChange,
    )

logger = logging.getLogger(__name__)

validate_crypto_asset_change_settings()


def publish_crypto_asset_change(change: CryptoAssetChange) -> None:
    """`XADD` события в стрим изменений `CryptoAsset`, с потолком по длине."""
    timeout = settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_PUBLISH_TIMEOUT_SECONDS
    client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
    )
    try:
        message_id = client.xadd(
            settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_STREAM_KEY,
            serialize_crypto_asset_change(change),  # type: ignore[arg-type]
            maxlen=settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_MAXLEN,
            approximate=True,
        )
    except RedisError:
        logger.exception(
            f"Событие изменения CryptoAsset не отправлено в Redis "
            f"(asset_id={change.asset_id}, kind={change.kind}, "
            f"пара={change.trading_pair}): stream_binance подхватит изменение "
            f"при следующем событии или после восстановления своего "
            f"соединения с Redis",
        )
    else:
        logger.info(
            f"Событие {change.kind} по {change.trading_pair} "
            f"(asset_id={change.asset_id}) отправлено в Redis для stream_binance "
            f"(id={message_id!r})",
        )
    finally:
        client.close()
