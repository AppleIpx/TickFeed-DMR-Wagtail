from __future__ import annotations

import logging
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, patch

import msgspec
import pytest
from asgiref.sync import sync_to_async
from django.conf import settings

from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.daily_candles import (
    crypto as crypto_daily_candles,
)
from tickfeeddmr.market_data.services.daily_candles import fiat as fiat_daily_candles
from tickfeeddmr.market_data.services.daily_candles import stock as stock_daily_candles
from tickfeeddmr.market_data.services.locks import redis_lock
from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    FiatCurrencyFactory,
    StockAssetFactory,
)

pytestmark = pytest.mark.django_db(transaction=True)

LOCK_TTL_SECONDS = 30


class DomainCase(msgspec.Struct, frozen=True):
    module: ModuleType
    factory: Any
    client_target: str
    failing_method: str
    unavailable_log_snippet: str


CASES = [
    DomainCase(
        module=crypto_daily_candles,
        factory=CryptoAssetFactory,
        client_target=(
            "tickfeeddmr.market_data.services.daily_candles.crypto.BinanceRestClient"
        ),
        failing_method="get_daily_candles",
        unavailable_log_snippet="Binance недоступен",
    ),
    DomainCase(
        module=stock_daily_candles,
        factory=StockAssetFactory,
        client_target=(
            "tickfeeddmr.market_data.services.daily_candles.stock.MoexIssClient"
        ),
        failing_method="get_candle_borders",
        unavailable_log_snippet="MOEX ISS недоступен",
    ),
    DomainCase(
        module=fiat_daily_candles,
        factory=FiatCurrencyFactory,
        client_target=(
            "tickfeeddmr.market_data.services.daily_candles.fiat.CbrDailyRatesClient"
        ),
        failing_method="get_dynamic_rates",
        unavailable_log_snippet="ЦБ РФ недоступен",
    ),
]

CASE_IDS = ["crypto", "stock", "fiat"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_catch_up_all_assets_skips_when_no_active_assets(
    case: DomainCase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        patch(case.client_target) as client_cls,
        caplog.at_level(logging.INFO),
    ):
        result = await case.module.catch_up_all_assets(limit=10)

    client_cls.assert_not_called()
    assert result is not None
    assert result.processed == 0
    assert result.written == 0
    assert result.budget_exhausted is False
    assert any("собирать нечего" in r.message for r in caplog.records)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_catch_up_all_assets_skips_when_lock_is_busy(
    case: DomainCase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _make_active_asset(case)

    async with redis_lock(
        redis_url=settings.REDIS_URL,
        key=case.module.LOCK_KEY,
        ttl_seconds=LOCK_TTL_SECONDS,
    ):
        with (
            patch(case.client_target) as client_cls,
            caplog.at_level(logging.INFO),
        ):
            result = await case.module.catch_up_all_assets(limit=10)

    client_cls.assert_not_called()
    assert result is None
    assert any("лок занят" in r.message for r in caplog.records)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_catch_up_all_assets_provider_error_on_one_asset_does_not_stop_run(
    case: DomainCase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _make_active_asset(case)
    await _make_active_asset(case)

    instance = AsyncMock()
    setattr(
        instance,
        case.failing_method,
        AsyncMock(side_effect=ProviderConnectionError("недоступно")),
    )
    instance.aclose = AsyncMock()

    with (
        patch(case.client_target, return_value=instance),
        caplog.at_level(logging.WARNING),
    ):
        result = await case.module.catch_up_all_assets(
            limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
        )

    assert result is not None
    assert result.processed == 0
    assert result.written == 0
    assert result.skipped_errors == 2  # noqa: PLR2004
    assert result.budget_exhausted is False
    assert any(case.unavailable_log_snippet in r.message for r in caplog.records)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_catch_up_all_assets_unexpected_error_on_one_asset_does_not_stop_run(
    case: DomainCase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Регрессия: не только `ProviderConnectionError` не должен прерывать batch.

    Любое другое исключение (например, испорченная строка от источника)
    раньше вылетало из цикла `_run` и обрывало обработку всех оставшихся
    активов прогона — см. фикс `except Exception` в `_run`.
    """
    await _make_active_asset(case)
    await _make_active_asset(case)

    instance = AsyncMock()
    setattr(
        instance,
        case.failing_method,
        AsyncMock(side_effect=ValueError("испорченные данные источника")),
    )
    instance.aclose = AsyncMock()

    with (
        patch(case.client_target, return_value=instance),
        caplog.at_level(logging.WARNING),
    ):
        result = await case.module.catch_up_all_assets(
            limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
        )

    assert result is not None
    assert result.processed == 0
    assert result.written == 0
    assert result.skipped_errors == 2  # noqa: PLR2004
    assert result.budget_exhausted is False
    assert any("Не удалось догнать" in r.message for r in caplog.records)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_catch_up_all_assets_stops_remaining_when_budget_exhausted(
    case: DomainCase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _make_active_asset(case)
    await _make_active_asset(case)

    with (
        patch(case.client_target) as client_cls,
        patch.object(case.module, "RunBudget") as budget_cls,
        caplog.at_level(logging.INFO),
    ):
        budget_cls.return_value.expired = True
        result = await case.module.catch_up_all_assets(
            limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
        )

    client_cls.assert_not_called()
    assert result is not None
    assert result.processed == 0
    assert result.budget_exhausted is True
    assert any("бюджет прогона исчерпан" in r.message for r in caplog.records)


async def _make_active_asset(case: DomainCase) -> None:
    await sync_to_async(case.factory.create)()
