import logging
from typing import TYPE_CHECKING

from django.db import transaction

from tickfeeddmr.market_data.services.crypto_asset_changes.publisher import (
    publish_crypto_asset_change,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.schemas import (
    CryptoAssetChange,
)

if TYPE_CHECKING:
    from collections.abc import Collection

    from tickfeeddmr.market_data.models import CryptoAsset
    from tickfeeddmr.market_data.services.crypto_asset_changes.schemas import (
        CryptoAssetChangeKind,
    )

logger = logging.getLogger(__name__)


def publish_crypto_asset_save_on_commit(
    asset: CryptoAsset,
    *,
    created: bool,
    raw: bool,
    update_fields: Collection[str] | None,
) -> None:
    """Сообщить `stream_binance`, что набор подписанных пар мог измениться.

    Только создание или изменение `exchange`/`trading_pair`/`is_active` —
    сохранение без изменения этих полей событие не шлёт.
    """
    if raw:
        return
    if created:
        kind: CryptoAssetChangeKind = "created"
    elif asset.subscription_fields_changed(update_fields):
        kind = "updated"
    else:
        return
    asset.remember_subscription_fields()
    _publish_on_commit(asset, kind)


def publish_crypto_asset_deletion_on_commit(asset: CryptoAsset) -> None:
    _publish_on_commit(asset, "deleted")


def _publish_on_commit(asset: CryptoAsset, kind: CryptoAssetChangeKind) -> None:
    deferred = asset.get_deferred_fields()
    change = CryptoAssetChange(
        asset_id=asset.pk,
        kind=kind,
        exchange="" if "exchange" in deferred else asset.exchange,
        trading_pair="" if "trading_pair" in deferred else asset.trading_pair,
    )
    logger.info(
        f"Крипто-актив id={change.asset_id} ({change.trading_pair}): {kind}, "
        f"событие для stream_binance после коммита",
    )
    transaction.on_commit(lambda: publish_crypto_asset_change(change))
