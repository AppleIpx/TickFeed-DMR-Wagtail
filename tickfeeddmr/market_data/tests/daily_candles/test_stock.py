from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.providers.moex.client import CANDLES_PAGE_ROWS
from tickfeeddmr.market_data.providers.moex.types import MoexCandleRow
from tickfeeddmr.market_data.services.daily_candles import stock as stock_daily_candles
from tickfeeddmr.market_data.services.daily_candles.stock import (
    _fetch_all_pages,
    _moscow_midnight,
)
from tickfeeddmr.market_data.tests.factories import StockDailyCandleFactory

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import StockAsset

pytestmark = pytest.mark.django_db(transaction=True)

CLIENT_TARGET = "tickfeeddmr.market_data.services.daily_candles.stock.MoexIssClient"


def _candle(day: date, *, price: str = "250.55") -> MoexCandleRow:
    return MoexCandleRow(
        open=Decimal(price),
        high=Decimal(price),
        low=Decimal(price),
        close=Decimal(price),
        value=Decimal("1000.00"),
        volume=100,
        begin=_moscow_midnight(day),
        end=_moscow_midnight(day) + timedelta(hours=23, minutes=59, seconds=59),
    )


def _mock_client(
    rows: list[MoexCandleRow],
    *,
    borders: tuple[date, date] = (date(2007, 5, 11), date(2026, 9, 17)),
) -> AsyncMock:
    instance = AsyncMock()
    instance.get_candle_borders = AsyncMock(return_value=borders)
    instance.get_candles = AsyncMock(return_value=rows)
    instance.aclose = AsyncMock()
    return instance


async def test_catch_up_asset_cold_start_uses_candle_borders(
    stock_asset: StockAsset,
) -> None:
    instance = _mock_client(
        [_candle(date(2026, 9, 17))],
        borders=(date(2010, 3, 1), date(2026, 9, 17)),
    )
    with patch(CLIENT_TARGET, return_value=instance) as client_cls:
        result = await stock_daily_candles.catch_up_asset(
            stock_asset,
            until=date(2026, 9, 17),
        )

    client_cls.assert_called_once()
    instance.get_candle_borders.assert_awaited_once_with(
        stock_asset.symbol,
        interval=stock_daily_candles.DAILY_CANDLE_INTERVAL,
    )
    instance.get_candles.assert_awaited_once_with(
        stock_asset.symbol,
        start=_moscow_midnight(date(2010, 3, 1)),
        end=_moscow_midnight(date(2026, 9, 17)),
        interval=stock_daily_candles.DAILY_CANDLE_INTERVAL,
        start_index=0,
    )
    assert result.written == 1
    assert result.already_up_to_date is False
    assert await stock_daily_candles.StockDailyCandle.objects.acount() == 1


async def test_catch_up_asset_resumes_from_day_after_last_candle_without_borders_call(
    stock_asset: StockAsset,
) -> None:
    await sync_to_async(StockDailyCandleFactory.create)(
        asset=stock_asset,
        date=date(2026, 9, 10),
    )
    instance = _mock_client([_candle(date(2026, 9, 17))])

    with patch(CLIENT_TARGET, return_value=instance):
        result = await stock_daily_candles.catch_up_asset(
            stock_asset,
            until=date(2026, 9, 17),
        )

    instance.get_candle_borders.assert_not_awaited()
    instance.get_candles.assert_awaited_once_with(
        stock_asset.symbol,
        start=_moscow_midnight(date(2026, 9, 11)),
        end=_moscow_midnight(date(2026, 9, 17)),
        interval=stock_daily_candles.DAILY_CANDLE_INTERVAL,
        start_index=0,
    )
    assert result.written == 1
    assert await stock_daily_candles.StockDailyCandle.objects.acount() == 2  # noqa: PLR2004


async def test_catch_up_asset_already_up_to_date_skips_client_entirely(
    stock_asset: StockAsset,
) -> None:
    await sync_to_async(StockDailyCandleFactory.create)(
        asset=stock_asset,
        date=date(2026, 9, 17),
    )

    with patch(CLIENT_TARGET) as client_cls:
        result = await stock_daily_candles.catch_up_asset(
            stock_asset,
            until=date(2026, 9, 17),
        )

    client_cls.assert_not_called()
    assert result.written == 0
    assert result.already_up_to_date is True


async def test_catch_up_asset_ignores_conflicting_duplicate_rows(
    stock_asset: StockAsset,
) -> None:
    first_instance = _mock_client([_candle(date(2026, 9, 10))])
    with patch(CLIENT_TARGET, return_value=first_instance):
        await stock_daily_candles.catch_up_asset(stock_asset, until=date(2026, 9, 10))

    second_instance = _mock_client(
        [_candle(date(2026, 9, 10)), _candle(date(2026, 9, 11))],
    )
    with patch(CLIENT_TARGET, return_value=second_instance):
        await stock_daily_candles.catch_up_asset(stock_asset, until=date(2026, 9, 11))

    assert await stock_daily_candles.StockDailyCandle.objects.acount() == 2  # noqa: PLR2004
    dates = {
        row
        async for row in stock_daily_candles.StockDailyCandle.objects.filter(
            asset=stock_asset,
        ).values_list("date", flat=True)
    }
    assert dates == {date(2026, 9, 10), date(2026, 9, 11)}


async def test_fetch_all_pages_single_page_when_batch_below_limit() -> None:
    instance = AsyncMock()
    rows = [_candle(date(2026, 9, 1)), _candle(date(2026, 9, 2))]
    instance.get_candles = AsyncMock(return_value=rows)

    result = await _fetch_all_pages(
        instance,
        "SBER",
        start=_moscow_midnight(date(2026, 9, 1)),
        end=_moscow_midnight(date(2026, 9, 10)),
    )

    assert result == rows
    instance.get_candles.assert_awaited_once()


async def test_fetch_all_pages_requests_second_page_when_batch_is_full() -> None:
    first_page = [
        _candle(date(2020, 1, 1) + timedelta(days=n)) for n in range(CANDLES_PAGE_ROWS)
    ]
    second_page = [_candle(first_page[-1].begin.date() + timedelta(days=1))]
    instance = AsyncMock()
    instance.get_candles = AsyncMock(side_effect=[first_page, second_page])

    result = await _fetch_all_pages(
        instance,
        "SBER",
        start=_moscow_midnight(date(2020, 1, 1)),
        end=_moscow_midnight(date(2025, 1, 1)),
    )

    assert len(result) == CANDLES_PAGE_ROWS + 1
    assert instance.get_candles.await_count == 2  # noqa: PLR2004
    second_call_kwargs = instance.get_candles.await_args_list[1].kwargs
    assert second_call_kwargs["start_index"] == CANDLES_PAGE_ROWS
