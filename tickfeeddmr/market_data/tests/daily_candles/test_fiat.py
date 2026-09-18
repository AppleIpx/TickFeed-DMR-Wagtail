from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.providers.cbr.types import CbrHistoryRateRow
from tickfeeddmr.market_data.services.daily_candles import fiat as fiat_daily_candles
from tickfeeddmr.market_data.services.daily_candles.fiat import (
    DENOMINATION_DATE,
    HISTORY_START_DATE,
    _denominated_rate,
)
from tickfeeddmr.market_data.tests.factories import FiatPriceSnapshotFactory

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import FiatCurrency

pytestmark = pytest.mark.django_db(transaction=True)

CLIENT_TARGET = (
    "tickfeeddmr.market_data.services.daily_candles.fiat.CbrDailyRatesClient"
)


@pytest.mark.parametrize(
    ("effective_date", "rate", "expected"),
    [
        (date(1997, 12, 30), Decimal("5960.00"), Decimal("5.96")),
        (date(1998, 1, 1), Decimal("5.96"), Decimal("5.96")),
        (date(1998, 1, 2), Decimal("5.98"), Decimal("5.98")),
    ],
)
def test_denominated_rate_boundary(
    effective_date: date,
    rate: Decimal,
    expected: Decimal,
) -> None:
    assert _denominated_rate(rate, effective_date) == expected


def test_denomination_date_is_first_of_january_1998() -> None:
    assert date(1998, 1, 1) == DENOMINATION_DATE


def _row(day: date, *, rate: str = "91.1234") -> CbrHistoryRateRow:
    return CbrHistoryRateRow(effective_date=day, rate=Decimal(rate))


def _mock_client(rows: list[CbrHistoryRateRow]) -> AsyncMock:
    instance = AsyncMock()
    instance.get_dynamic_rates = AsyncMock(return_value=rows)
    instance.aclose = AsyncMock()
    return instance


async def test_catch_up_asset_cold_start_requests_from_history_start(
    fiat_currency: FiatCurrency,
) -> None:
    instance = _mock_client([_row(date(2026, 9, 17))])
    with patch(CLIENT_TARGET, return_value=instance) as client_cls:
        result = await fiat_daily_candles.catch_up_asset(
            fiat_currency,
            until=date(2026, 9, 17),
        )

    client_cls.assert_called_once()
    instance.get_dynamic_rates.assert_awaited_once_with(
        fiat_currency.cbr_id,
        date_from=HISTORY_START_DATE,
        date_to=date(2026, 9, 17),
    )
    assert result.written == 1
    assert result.already_up_to_date is False
    assert await fiat_daily_candles.FiatPriceSnapshot.objects.acount() == 1


async def test_catch_up_asset_resumes_from_day_after_last_snapshot(
    fiat_currency: FiatCurrency,
) -> None:
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=date(2026, 9, 10),
    )
    instance = _mock_client([_row(date(2026, 9, 17))])

    with patch(CLIENT_TARGET, return_value=instance):
        result = await fiat_daily_candles.catch_up_asset(
            fiat_currency,
            until=date(2026, 9, 17),
        )

    instance.get_dynamic_rates.assert_awaited_once_with(
        fiat_currency.cbr_id,
        date_from=date(2026, 9, 11),
        date_to=date(2026, 9, 17),
    )
    assert result.written == 1
    assert await fiat_daily_candles.FiatPriceSnapshot.objects.acount() == 2  # noqa: PLR2004


async def test_catch_up_asset_already_up_to_date_skips_client_entirely(
    fiat_currency: FiatCurrency,
) -> None:
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=date(2026, 9, 17),
    )

    with patch(CLIENT_TARGET) as client_cls:
        result = await fiat_daily_candles.catch_up_asset(
            fiat_currency,
            until=date(2026, 9, 17),
        )

    client_cls.assert_not_called()
    assert result.written == 0
    assert result.already_up_to_date is True


async def test_catch_up_asset_ignores_conflicting_duplicate_rows(
    fiat_currency: FiatCurrency,
) -> None:
    first_instance = _mock_client([_row(date(2026, 9, 10))])
    with patch(CLIENT_TARGET, return_value=first_instance):
        await fiat_daily_candles.catch_up_asset(fiat_currency, until=date(2026, 9, 10))

    second_instance = _mock_client([_row(date(2026, 9, 10)), _row(date(2026, 9, 11))])
    with patch(CLIENT_TARGET, return_value=second_instance):
        await fiat_daily_candles.catch_up_asset(fiat_currency, until=date(2026, 9, 11))

    assert await fiat_daily_candles.FiatPriceSnapshot.objects.acount() == 2  # noqa: PLR2004
    dates = {
        row
        async for row in fiat_daily_candles.FiatPriceSnapshot.objects.filter(
            asset=fiat_currency,
        ).values_list("effective_date", flat=True)
    }
    assert dates == {date(2026, 9, 10), date(2026, 9, 11)}


async def test_catch_up_asset_applies_denomination_to_pre_1998_rates(
    fiat_currency: FiatCurrency,
) -> None:
    instance = _mock_client([_row(date(1997, 12, 30), rate="5960.00")])
    with patch(CLIENT_TARGET, return_value=instance):
        await fiat_daily_candles.catch_up_asset(fiat_currency, until=date(1997, 12, 30))

    snapshot = await fiat_daily_candles.FiatPriceSnapshot.objects.aget(
        asset=fiat_currency,
    )
    assert snapshot.price == Decimal("5.96")
    assert snapshot.timestamp == datetime.combine(
        date(1997, 12, 30),
        datetime.min.time(),
        tzinfo=fiat_daily_candles.MOSCOW_TZ,
    ).astimezone(UTC)
