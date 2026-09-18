from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import msgspec
import pytest
from celery.exceptions import Retry
from django.conf import settings

from tickfeeddmr.market_data import tasks
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.daily_candles.types import CatchUpResult
from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    FiatCurrencyFactory,
    StockAssetFactory,
)

pytestmark = pytest.mark.django_db(transaction=True)


class DomainCase(msgspec.Struct, frozen=True):
    factory: Any
    asset_task_name: str
    all_task_name: str
    catch_up_asset_target: str
    catch_up_all_assets_target: str
    result: Any


CASES = [
    DomainCase(
        factory=CryptoAssetFactory,
        asset_task_name="catch_up_crypto_asset_history",
        all_task_name="catch_up_all_crypto_daily_candles",
        catch_up_asset_target=(
            "tickfeeddmr.market_data.services.daily_candles.crypto.catch_up_asset"
        ),
        catch_up_all_assets_target=(
            "tickfeeddmr.market_data.services.daily_candles.crypto.catch_up_all_assets"
        ),
        result=CatchUpResult(written=1, already_up_to_date=False),
    ),
    DomainCase(
        factory=StockAssetFactory,
        asset_task_name="catch_up_stock_asset_history",
        all_task_name="catch_up_all_stock_daily_candles",
        catch_up_asset_target=(
            "tickfeeddmr.market_data.services.daily_candles.stock.catch_up_asset"
        ),
        catch_up_all_assets_target=(
            "tickfeeddmr.market_data.services.daily_candles.stock.catch_up_all_assets"
        ),
        result=CatchUpResult(written=1, already_up_to_date=False),
    ),
    DomainCase(
        factory=FiatCurrencyFactory,
        asset_task_name="catch_up_fiat_asset_history",
        all_task_name="catch_up_all_fiat_daily_candles",
        catch_up_asset_target=(
            "tickfeeddmr.market_data.services.daily_candles.fiat.catch_up_asset"
        ),
        catch_up_all_assets_target=(
            "tickfeeddmr.market_data.services.daily_candles.fiat.catch_up_all_assets"
        ),
        result=CatchUpResult(written=1, already_up_to_date=False),
    ),
]
CASE_IDS = ["crypto", "stock", "fiat"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_asset_history_task_calls_service_with_resolved_asset(case: DomainCase) -> None:
    asset = case.factory.create()
    task = getattr(tasks, case.asset_task_name)

    with patch(
        case.catch_up_asset_target,
        AsyncMock(return_value=case.result),
    ) as service_call:
        task.apply(kwargs={"asset_id": asset.pk}, throw=True)

    service_call.assert_awaited_once()
    assert service_call.await_args is not None
    called_asset = service_call.await_args.args[0]
    assert called_asset.pk == asset.pk


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_asset_history_task_retries_on_provider_connection_error(
    case: DomainCase,
) -> None:
    """`autoretry_for=(ProviderConnectionError,)` должен обернуть её в `Retry`,
    а не дать упасть как обычному необработанному исключению.

    В eager-режиме `self.retry()` не выполняет задачу повторно сам —
    он поднимает `celery.exceptions.Retry` (это же происходит и в реальном
    воркере: `Retry` сигнализирует брокеру переотправить таск в очередь).
    Здесь важно только то, что именно `ProviderConnectionError` доходит до
    `self.retry()`, а не падает мимо него.
    """
    asset = case.factory.create()
    task = getattr(tasks, case.asset_task_name)

    with (
        patch(
            case.catch_up_asset_target,
            AsyncMock(side_effect=ProviderConnectionError("недоступно")),
        ) as service_call,
        pytest.raises(Retry),
    ):
        task.apply(kwargs={"asset_id": asset.pk}, throw=True)

    service_call.assert_awaited_once()


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_all_daily_candles_task_delegates_with_settings_limit(case: DomainCase) -> None:
    task = getattr(tasks, case.all_task_name)

    with patch(
        case.catch_up_all_assets_target,
        AsyncMock(return_value=None),
    ) as service_call:
        task.apply(throw=True)

    service_call.assert_awaited_once_with(
        limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
    )
