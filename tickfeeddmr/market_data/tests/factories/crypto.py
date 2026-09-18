from __future__ import annotations

from decimal import Decimal

import factory
from django.utils import timezone

from tickfeeddmr.market_data.models import (
    CryptoAsset,
    CryptoDailyCandle,
    CryptoPriceSnapshot,
)


class CryptoAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CryptoAsset

    symbol = factory.Sequence(lambda n: f"CRYPTO{n}")
    display_name = factory.Faker("word")
    exchange = "BINANCE"
    trading_pair = factory.Sequence(lambda n: f"PAIR{n}")
    provider_asset_id = ""


class CryptoPriceSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CryptoPriceSnapshot

    asset = factory.SubFactory(CryptoAssetFactory)
    price = Decimal("42000.12345678")
    volume = Decimal("1.5")
    timestamp = factory.LazyFunction(timezone.now)


class CryptoDailyCandleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CryptoDailyCandle

    asset = factory.SubFactory(CryptoAssetFactory)
    date = factory.LazyFunction(lambda: timezone.now().date())
    open = Decimal("42000.00000000")
    high = Decimal("42500.00000000")
    low = Decimal("41500.00000000")
    close = Decimal("42200.00000000")
    volume = Decimal("100.00000000")
