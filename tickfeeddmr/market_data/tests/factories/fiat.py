from __future__ import annotations

from decimal import Decimal

import factory
from django.utils import timezone

from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot, FiatSource


class FiatCurrencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FiatCurrency

    symbol = factory.Sequence(lambda n: f"FIAT{n}")
    display_name = factory.Faker("word")
    iso_code = factory.Sequence(lambda n: f"X{n:02d}")
    moex_secid = ""
    source = FiatSource.MOEX


class FiatPriceSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FiatPriceSnapshot

    asset = factory.SubFactory(FiatCurrencyFactory)
    price = Decimal("91.123456")
    source = FiatSource.MOEX
    timestamp = factory.LazyFunction(timezone.now)
