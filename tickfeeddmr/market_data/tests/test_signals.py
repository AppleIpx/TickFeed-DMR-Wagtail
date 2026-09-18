from __future__ import annotations

from typing import Any

import msgspec
import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data import tasks
from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    FiatCurrencyFactory,
    StockAssetFactory,
)

pytestmark = pytest.mark.django_db(transaction=True)


class DomainCase(msgspec.Struct, frozen=True):
    factory: Any
    task_name: str


CASES = [
    DomainCase(CryptoAssetFactory, "catch_up_crypto_asset_history"),
    DomainCase(StockAssetFactory, "catch_up_stock_asset_history"),
    DomainCase(FiatCurrencyFactory, "catch_up_fiat_asset_history"),
]
CASE_IDS = ["crypto", "stock", "fiat"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_creating_asset_queues_signal_catch_up_with_its_id(
    case: DomainCase,
) -> None:
    task = getattr(tasks, case.task_name)

    asset = await sync_to_async(case.factory.create)()

    task.delay.assert_called_once_with(asset_id=asset.pk)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_updating_existing_asset_does_not_queue_signal_catch_up(
    case: DomainCase,
) -> None:
    task = getattr(tasks, case.task_name)
    asset = await sync_to_async(case.factory.create)()
    task.delay.reset_mock()

    asset.display_name = "updated"
    await sync_to_async(asset.save)(update_fields=["display_name"])

    task.delay.assert_not_called()
