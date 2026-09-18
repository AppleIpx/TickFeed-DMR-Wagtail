from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.providers.binance.rest import MAX_KLINES_LIMIT
from tickfeeddmr.market_data.providers.binance.types import BinanceCandleRow
from tickfeeddmr.market_data.services.daily_candles import (
    crypto as crypto_daily_candles,
)
from tickfeeddmr.market_data.services.daily_candles.crypto import (
    EPOCH_START,
    _fetch_all_pages,
    _moscow_midnight,
)
from tickfeeddmr.market_data.tests.factories import CryptoDailyCandleFactory

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = pytest.mark.django_db(transaction=True)

CLIENT_TARGET = (
    "tickfeeddmr.market_data.services.daily_candles.crypto.BinanceRestClient"
)


def _row(day: date, *, price: str = "50000.00") -> BinanceCandleRow:
    return BinanceCandleRow(
        date=day,
        open=Decimal(price),
        high=Decimal(price),
        low=Decimal(price),
        close=Decimal(price),
        volume=Decimal("1.0"),
    )


def _mock_client(rows: list[BinanceCandleRow]) -> AsyncMock:
    instance = AsyncMock()
    instance.get_daily_candles = AsyncMock(return_value=rows)
    instance.aclose = AsyncMock()
    return instance


async def test_catch_up_asset_cold_start_requests_from_epoch(
    crypto_asset: CryptoAsset,
) -> None:
    instance = _mock_client([_row(date(2026, 9, 17))])
    with patch(CLIENT_TARGET, return_value=instance) as client_cls:
        result = await crypto_daily_candles.catch_up_asset(
            crypto_asset,
            until=date(2026, 9, 17),
        )

    client_cls.assert_called_once()
    instance.get_daily_candles.assert_awaited_once_with(
        crypto_asset.trading_pair,
        start_time=EPOCH_START,
        end_time=_moscow_midnight(date(2026, 9, 17)),
    )
    assert result.written == 1
    assert result.already_up_to_date is False
    assert await crypto_daily_candles.CryptoDailyCandle.objects.acount() == 1


async def test_catch_up_asset_resumes_from_day_after_last_candle(
    crypto_asset: CryptoAsset,
) -> None:
    await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=date(2026, 9, 10),
    )
    instance = _mock_client([_row(date(2026, 9, 17))])

    with patch(CLIENT_TARGET, return_value=instance):
        result = await crypto_daily_candles.catch_up_asset(
            crypto_asset,
            until=date(2026, 9, 17),
        )

    instance.get_daily_candles.assert_awaited_once_with(
        crypto_asset.trading_pair,
        start_time=_moscow_midnight(date(2026, 9, 11)),
        end_time=_moscow_midnight(date(2026, 9, 17)),
    )
    assert result.written == 1
    assert await crypto_daily_candles.CryptoDailyCandle.objects.acount() == 2  # noqa: PLR2004


async def test_catch_up_asset_already_up_to_date_skips_client_entirely(
    crypto_asset: CryptoAsset,
) -> None:
    await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=date(2026, 9, 17),
    )

    with patch(CLIENT_TARGET) as client_cls:
        result = await crypto_daily_candles.catch_up_asset(
            crypto_asset,
            until=date(2026, 9, 17),
        )

    client_cls.assert_not_called()
    assert result.written == 0
    assert result.already_up_to_date is True


async def test_catch_up_asset_ignores_conflicting_duplicate_rows(
    crypto_asset: CryptoAsset,
) -> None:
    """Источник может повторно прислать уже сохранённый день — `ignore_conflicts`
    не должен превращать это в ошибку уникальности или задвоение строк."""
    first_instance = _mock_client([_row(date(2026, 9, 10))])
    with patch(CLIENT_TARGET, return_value=first_instance):
        await crypto_daily_candles.catch_up_asset(crypto_asset, until=date(2026, 9, 10))

    # Второй прогон запрашивает более широкий диапазон, но источник (для
    # теста) снова отдаёт уже сохранённый день вперемешку с новым.
    second_instance = _mock_client(
        [_row(date(2026, 9, 10)), _row(date(2026, 9, 11))],
    )
    with patch(CLIENT_TARGET, return_value=second_instance):
        result = await crypto_daily_candles.catch_up_asset(
            crypto_asset,
            until=date(2026, 9, 11),
        )

    assert result.written == 2  # noqa: PLR2004 — bulk_create call size, не итоговый count
    assert await crypto_daily_candles.CryptoDailyCandle.objects.acount() == 2  # noqa: PLR2004
    dates = {
        row
        async for row in crypto_daily_candles.CryptoDailyCandle.objects.filter(
            asset=crypto_asset,
        ).values_list("date", flat=True)
    }
    assert dates == {date(2026, 9, 10), date(2026, 9, 11)}


async def test_fetch_all_pages_single_page_when_batch_below_limit() -> None:
    instance = AsyncMock()
    rows = [_row(date(2026, 9, 1)), _row(date(2026, 9, 2))]
    instance.get_daily_candles = AsyncMock(return_value=rows)

    result = await _fetch_all_pages(
        instance,
        "BTCUSDT",
        _moscow_midnight(date(2026, 9, 1)),
        _moscow_midnight(date(2026, 9, 10)),
    )

    assert result == rows
    instance.get_daily_candles.assert_awaited_once()


async def test_fetch_all_pages_requests_second_page_when_batch_is_full() -> None:
    first_page = [
        _row(date(2020, 1, 1) + timedelta(days=n)) for n in range(MAX_KLINES_LIMIT)
    ]
    second_page = [_row(first_page[-1].date + timedelta(days=1))]
    instance = AsyncMock()
    instance.get_daily_candles = AsyncMock(side_effect=[first_page, second_page])

    result = await _fetch_all_pages(
        instance,
        "BTCUSDT",
        _moscow_midnight(date(2020, 1, 1)),
        _moscow_midnight(date(2025, 1, 1)),
    )

    assert len(result) == MAX_KLINES_LIMIT + 1
    assert instance.get_daily_candles.await_count == 2  # noqa: PLR2004
    second_call_kwargs = instance.get_daily_candles.await_args_list[1].kwargs
    assert second_call_kwargs["start_time"] == _moscow_midnight(
        first_page[-1].date + timedelta(days=1),
    )
