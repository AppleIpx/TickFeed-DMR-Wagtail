import logging
from typing import TYPE_CHECKING

from django.db import transaction

from tickfeeddmr.market_data.tasks import (
    catch_up_crypto_asset_history,
    catch_up_fiat_asset_history,
    catch_up_stock_asset_history,
)

if TYPE_CHECKING:
    from celery import Task

    from tickfeeddmr.market_data.models import (
        AssetBase,
        CryptoAsset,
        FiatCurrency,
        StockAsset,
    )

logger = logging.getLogger(__name__)


def queue_crypto_asset_history_catch_up(
    asset: CryptoAsset,
    *,
    created: bool,
    raw: bool,
) -> None:
    """Поставить догон дневных свечей нового `CryptoAsset` после коммита."""
    _queue_on_create(
        asset,
        created=created,
        raw=raw,
        task=catch_up_crypto_asset_history,
        subject="Новый крипто-актив",
    )


def queue_stock_asset_history_catch_up(
    asset: StockAsset,
    *,
    created: bool,
    raw: bool,
) -> None:
    """Поставить догон дневных свечей новой `StockAsset` после коммита."""
    _queue_on_create(
        asset,
        created=created,
        raw=raw,
        task=catch_up_stock_asset_history,
        subject="Новая бумага",
    )


def queue_fiat_asset_history_catch_up(
    asset: FiatCurrency,
    *,
    created: bool,
    raw: bool,
) -> None:
    """Поставить догон дневных свечей новой `FiatCurrency` после коммита."""
    _queue_on_create(
        asset,
        created=created,
        raw=raw,
        task=catch_up_fiat_asset_history,
        subject="Новая валюта",
    )


def _queue_on_create(
    asset: AssetBase,
    *,
    created: bool,
    raw: bool,
    task: Task,
    subject: str,
) -> None:
    """Только создание, не загрузка фикстуры (`raw`): изменение догон не ставит."""
    if not created or raw:
        return
    logger.info(
        f"{subject} {asset.symbol} (id={asset.pk}): "
        f"постановка сигнального догона истории в очередь после коммита",
    )
    transaction.on_commit(lambda: task.delay(asset_id=asset.pk))
