from typing import TYPE_CHECKING

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from tickfeeddmr.market_data.models import CryptoAsset, FiatCurrency, StockAsset
from tickfeeddmr.market_data.services.crypto_asset_changes.triggers import (
    publish_crypto_asset_deletion_on_commit,
    publish_crypto_asset_save_on_commit,
)
from tickfeeddmr.market_data.services.daily_candles import signal_catch_up

if TYPE_CHECKING:
    from collections.abc import Collection


@receiver(post_save, sender=CryptoAsset)
def queue_crypto_asset_history_catch_up(
    *,
    instance: CryptoAsset,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    signal_catch_up.queue_crypto_asset_history_catch_up(
        instance,
        created=created,
        raw=raw,
    )


@receiver(post_save, sender=CryptoAsset)
def publish_crypto_asset_subscription_change(
    *,
    instance: CryptoAsset,
    created: bool,
    raw: bool,
    update_fields: Collection[str] | None,
    **kwargs: object,
) -> None:
    publish_crypto_asset_save_on_commit(
        instance,
        created=created,
        raw=raw,
        update_fields=update_fields,
    )


@receiver(post_delete, sender=CryptoAsset)
def publish_crypto_asset_deletion(
    *,
    instance: CryptoAsset,
    **kwargs: object,
) -> None:
    publish_crypto_asset_deletion_on_commit(instance)


@receiver(post_save, sender=StockAsset)
def queue_stock_asset_history_catch_up(
    *,
    instance: StockAsset,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    signal_catch_up.queue_stock_asset_history_catch_up(
        instance,
        created=created,
        raw=raw,
    )


@receiver(post_save, sender=FiatCurrency)
def queue_fiat_asset_history_catch_up(
    *,
    instance: FiatCurrency,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    signal_catch_up.queue_fiat_asset_history_catch_up(
        instance,
        created=created,
        raw=raw,
    )
