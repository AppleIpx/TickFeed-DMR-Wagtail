from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async
from django.test import override_settings

from tickfeeddmr.market_data.services.queries.crypto import get_history, get_intraday
from tickfeeddmr.market_data.services.queries.errors import AssetNotFoundError
from tickfeeddmr.market_data.tests.factories import (
    CryptoDailyCandleFactory,
    CryptoPriceSnapshotFactory,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = pytest.mark.django_db(transaction=True)


async def test_get_intraday_aggregates_last_price_and_summed_volume_per_minute(
    crypto_asset: CryptoAsset,
) -> None:
    minute = datetime.now(UTC).replace(second=0, microsecond=0)
    await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        timestamp=minute,
        price=Decimal("100"),
        volume=Decimal("1"),
    )
    await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        timestamp=minute + timedelta(seconds=20),
        price=Decimal("101"),
        volume=Decimal("2"),
    )
    await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        timestamp=minute + timedelta(seconds=40),
        price=Decimal("102"),
        volume=Decimal("3"),
    )

    points = await get_intraday(crypto_asset.symbol)

    assert len(points) == 1
    point = points[0]
    assert point.timestamp == minute
    assert point.price == Decimal("102")
    assert point.volume == Decimal("6")


async def test_get_intraday_excludes_snapshots_outside_24h_window(
    crypto_asset: CryptoAsset,
) -> None:
    await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        timestamp=datetime.now(UTC) - timedelta(hours=25),
    )

    points = await get_intraday(crypto_asset.symbol)

    assert points == []


async def test_get_intraday_unknown_symbol_raises_asset_not_found() -> None:
    with pytest.raises(AssetNotFoundError):
        await get_intraday("UNKNOWN")


async def test_get_history_filters_by_period(crypto_asset: CryptoAsset) -> None:
    await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=datetime(2026, 1, 1, tzinfo=UTC).date(),
    )
    in_range = await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=datetime(2026, 6, 1, tzinfo=UTC).date(),
    )

    candles = await get_history(
        crypto_asset.symbol,
        date_from=datetime(2026, 3, 1, tzinfo=UTC).date(),
        date_to=datetime(2026, 12, 31, tzinfo=UTC).date(),
    )

    assert [candle.pk for candle in candles] == [in_range.pk]


async def test_get_history_unknown_symbol_raises_asset_not_found() -> None:
    with pytest.raises(AssetNotFoundError):
        await get_history("UNKNOWN", date_from=None, date_to=None)


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
async def test_get_history_defaults_to_earliest_candle_when_unconfigured(
    crypto_asset: CryptoAsset,
) -> None:
    """Без параметров и без настройки — вся история актива, а не последний год.

    Регрессия: у ETH в проде без параметров отдавало `today-365` вместо
    полной истории с 2017-08-17, потому что дефолт был захардкожен.
    """
    old_candle = await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=datetime(2017, 8, 17, tzinfo=UTC).date(),
    )
    recent_candle = await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=datetime.now(UTC).date(),
    )

    candles = await get_history(crypto_asset.symbol, date_from=None, date_to=None)

    assert {candle.pk for candle in candles} == {old_candle.pk, recent_candle.pk}


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
async def test_get_history_returns_empty_list_when_asset_has_no_candles(
    crypto_asset: CryptoAsset,
) -> None:
    candles = await get_history(crypto_asset.symbol, date_from=None, date_to=None)

    assert candles == []
