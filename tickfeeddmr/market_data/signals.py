import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from tickfeeddmr.market_data.models import CryptoAsset, FiatCurrency, StockAsset
from tickfeeddmr.market_data.tasks import (
    catch_up_crypto_asset_history,
    catch_up_fiat_asset_history,
    catch_up_stock_asset_history,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CryptoAsset)
def queue_crypto_asset_history_catch_up(
    *,
    instance: CryptoAsset,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    if not created or raw:
        return
    logger.info(
        f"Новый крипто-актив {instance.symbol} (id={instance.pk}): "
        f"постановка сигнального догона истории в очередь после коммита",
    )
    transaction.on_commit(
        lambda: catch_up_crypto_asset_history.delay(asset_id=instance.pk),
    )


@receiver(post_save, sender=StockAsset)
def queue_stock_asset_history_catch_up(
    *,
    instance: StockAsset,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    if not created or raw:
        return
    logger.info(
        f"Новая бумага {instance.symbol} (id={instance.pk}): "
        f"постановка сигнального догона истории в очередь после коммита",
    )
    transaction.on_commit(
        lambda: catch_up_stock_asset_history.delay(asset_id=instance.pk),
    )


@receiver(post_save, sender=FiatCurrency)
def queue_fiat_asset_history_catch_up(
    *,
    instance: FiatCurrency,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    if not created or raw:
        return
    logger.info(
        f"Новая валюта {instance.symbol} (id={instance.pk}): "
        f"постановка сигнального догона истории в очередь после коммита",
    )
    transaction.on_commit(
        lambda: catch_up_fiat_asset_history.delay(asset_id=instance.pk),
    )
