from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from tickfeeddmr.market_data import tasks
from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    CryptoPriceSnapshotFactory,
    FiatCurrencyFactory,
    FiatPriceSnapshotFactory,
    StockAssetFactory,
    StockPriceSnapshotFactory,
    StockTradeFactory,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import (
        CryptoAsset,
        CryptoPriceSnapshot,
        FiatCurrency,
        FiatPriceSnapshot,
        StockAsset,
        StockPriceSnapshot,
        StockTrade,
    )


_DAILY_CANDLES_CATCH_UP_TASK_NAMES = (
    "catch_up_crypto_asset_history",
    "catch_up_stock_asset_history",
    "catch_up_fiat_asset_history",
    "catch_up_all_crypto_daily_candles",
    "catch_up_all_stock_daily_candles",
    "catch_up_all_fiat_daily_candles",
)


@pytest.fixture(autouse=True)
def _mock_daily_candles_catch_up_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Не даёт сигналам реально ходить в сеть в тестах."""
    for task_name in _DAILY_CANDLES_CATCH_UP_TASK_NAMES:
        task = getattr(tasks, task_name)
        monkeypatch.setattr(task, "delay", MagicMock())
        monkeypatch.setattr(task, "apply_async", MagicMock())


@pytest.fixture
def crypto_asset(db) -> CryptoAsset:
    return CryptoAssetFactory.create()


@pytest.fixture
def fiat_currency(db) -> FiatCurrency:
    return FiatCurrencyFactory.create()


@pytest.fixture
def crypto_price_snapshot(db, crypto_asset: CryptoAsset) -> CryptoPriceSnapshot:
    return CryptoPriceSnapshotFactory.create(asset=crypto_asset)


@pytest.fixture
def fiat_price_snapshot(db, fiat_currency: FiatCurrency) -> FiatPriceSnapshot:
    return FiatPriceSnapshotFactory.create(asset=fiat_currency)


@pytest.fixture
def stock_asset(db) -> StockAsset:
    return StockAssetFactory.create()


@pytest.fixture
def stock_price_snapshot(db, stock_asset: StockAsset) -> StockPriceSnapshot:
    return StockPriceSnapshotFactory.create(asset=stock_asset)


@pytest.fixture
def stock_trade(db, stock_asset: StockAsset) -> StockTrade:
    return StockTradeFactory.create(asset=stock_asset)
