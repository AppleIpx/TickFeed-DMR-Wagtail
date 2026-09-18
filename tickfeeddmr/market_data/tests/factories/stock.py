from __future__ import annotations

from decimal import Decimal

import factory
from django.utils import timezone

from tickfeeddmr.market_data.models import (
    StockAsset,
    StockBoard,
    StockDailyCandle,
    StockPriceSnapshot,
    StockTrade,
    StockTradeSide,
)


class StockAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StockAsset

    symbol = factory.Sequence(lambda n: f"STOCK{n}")
    display_name = factory.Faker("word")
    board = StockBoard.TQBR
    track_trades = False
    last_trade_no = None


class StockPriceSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StockPriceSnapshot

    asset = factory.SubFactory(StockAssetFactory)
    last = Decimal("250.55")
    open = Decimal("248.10")
    high = Decimal("252.30")
    low = Decimal("247.00")
    change = Decimal("2.45")
    change_percent = Decimal("0.98")
    volume = 123_456
    value = Decimal("30000000.00")
    num_trades = 4200
    timestamp = factory.LazyFunction(timezone.now)


class StockTradeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StockTrade

    asset = factory.SubFactory(StockAssetFactory)
    trade_id = factory.Sequence(lambda n: n + 1)
    price = Decimal("250.55")
    quantity = 10
    side = StockTradeSide.BUY
    period = "N"
    timestamp = factory.LazyFunction(timezone.now)


class StockDailyCandleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StockDailyCandle

    asset = factory.SubFactory(StockAssetFactory)
    date = factory.LazyFunction(lambda: timezone.now().date())
    open = Decimal("248.10")
    high = Decimal("252.30")
    low = Decimal("247.00")
    close = Decimal("250.55")
    volume = 123_456
    value = Decimal("30000000.00")
