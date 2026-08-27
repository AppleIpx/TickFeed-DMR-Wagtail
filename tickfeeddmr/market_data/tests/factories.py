from __future__ import annotations

from decimal import Decimal

import factory
from django.utils import timezone

from tickfeeddmr.market_data.models import (
    CryptoAsset,
    CryptoPriceSnapshot,
    FiatCurrency,
    FiatPriceSnapshot,
    FiatSource,
)


class CryptoAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CryptoAsset

    symbol = factory.Sequence(lambda n: f"CRYPTO{n}")
    display_name = factory.Faker("word")
    exchange = "BINANCE"
    trading_pair = factory.Sequence(lambda n: f"PAIR{n}")
    provider_asset_id = ""


class FiatCurrencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FiatCurrency

    symbol = factory.Sequence(lambda n: f"FIAT{n}")
    display_name = factory.Faker("word")
    iso_code = factory.Sequence(lambda n: f"X{n:02d}")
    moex_secid = ""
    source = FiatSource.MOEX


class CryptoPriceSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CryptoPriceSnapshot

    asset = factory.SubFactory(CryptoAssetFactory)
    price = Decimal("42000.12345678")
    volume = Decimal("1.5")
    timestamp = factory.LazyFunction(timezone.now)


class FiatPriceSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FiatPriceSnapshot

    asset = factory.SubFactory(FiatCurrencyFactory)
    price = Decimal("91.123456")
    source = FiatSource.MOEX
    timestamp = factory.LazyFunction(timezone.now)
