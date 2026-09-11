from __future__ import annotations

from decimal import Decimal

import factory
from django.utils import timezone

from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot


class FiatCurrencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FiatCurrency

    symbol = factory.Sequence(lambda n: f"FIAT{n}")
    display_name = factory.Faker("word")
    iso_code = factory.Sequence(lambda n: f"X{n:02d}")
    cbr_id = factory.Sequence(lambda n: f"R{n:05d}")


class FiatPriceSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FiatPriceSnapshot

    asset = factory.SubFactory(FiatCurrencyFactory)
    price = Decimal("91.123456")
    effective_date = factory.LazyFunction(lambda: timezone.now().date())
    timestamp = factory.LazyFunction(timezone.now)
