from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    CryptoPriceSnapshotFactory,
    FiatCurrencyFactory,
    FiatPriceSnapshotFactory,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import (
        CryptoAsset,
        CryptoPriceSnapshot,
        FiatCurrency,
        FiatPriceSnapshot,
    )


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
