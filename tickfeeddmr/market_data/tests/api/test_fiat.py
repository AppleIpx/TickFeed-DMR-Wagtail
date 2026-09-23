from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async
from django.test import override_settings

from tickfeeddmr.market_data.tests.factories import (
    FiatCurrencyFactory,
    FiatPriceSnapshotFactory,
)

if TYPE_CHECKING:
    from dmr.test import DMRAsyncClient

    from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot

pytestmark = pytest.mark.django_db(transaction=True)


async def test_rates_returns_currency_with_snapshot(
    dmr_async_client: DMRAsyncClient,
    fiat_currency: FiatCurrency,
    fiat_price_snapshot: FiatPriceSnapshot,
) -> None:
    response = await dmr_async_client.get("/api/fiat/rates/")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["iso_code"] == fiat_currency.iso_code
    assert isinstance(item["rate"], str)
    assert Decimal(item["rate"]) == fiat_price_snapshot.price
    assert item["source"] == "ЦБ РФ"


async def test_rates_omits_currency_without_any_snapshot(
    dmr_async_client: DMRAsyncClient,
    fiat_currency: FiatCurrency,
    fiat_price_snapshot: FiatPriceSnapshot,
) -> None:
    await sync_to_async(FiatCurrencyFactory.create)()

    response = await dmr_async_client.get("/api/fiat/rates/")

    body = response.json()
    assert [item["iso_code"] for item in body] == [fiat_currency.iso_code]


async def test_rates_empty_when_no_currencies_have_snapshots(
    dmr_async_client: DMRAsyncClient,
) -> None:
    await sync_to_async(FiatCurrencyFactory.create)()

    response = await dmr_async_client.get("/api/fiat/rates/")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


async def test_history_unknown_iso_code_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/fiat/rates/UNKNOWN/history")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_history_from_after_to_returns_422(
    dmr_async_client: DMRAsyncClient,
    fiat_currency: FiatCurrency,
) -> None:
    response = await dmr_async_client.get(
        f"/api/fiat/rates/{fiat_currency.iso_code}/history"
        "?from=2026-09-18&to=2026-01-01",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_history_returns_rates_within_period(
    dmr_async_client: DMRAsyncClient,
    fiat_currency: FiatCurrency,
) -> None:
    snapshot = await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=datetime(2026, 6, 1, tzinfo=UTC).date(),
    )
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=datetime(2020, 1, 1, tzinfo=UTC).date(),
    )

    response = await dmr_async_client.get(
        f"/api/fiat/rates/{fiat_currency.iso_code}/history"
        "?from=2026-01-01&to=2026-12-31",
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["rate"] == str(snapshot.price)
    assert body[0]["effective_date"] == "2026-06-01"


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
async def test_history_without_params_defaults_to_earliest_rate_when_unconfigured(
    dmr_async_client: DMRAsyncClient,
    fiat_currency: FiatCurrency,
) -> None:
    """Без параметров и без настройки — вся история, а не последний год.

    Регрессия по образцу ETH в проде (см. `market_data/tests/api/
    test_queries_crypto.py`): курс старше года не должен отсекаться.
    """
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=datetime(2017, 8, 17, tzinfo=UTC).date(),
    )
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=datetime.now(UTC).date(),
    )

    response = await dmr_async_client.get(
        f"/api/fiat/rates/{fiat_currency.iso_code}/history",
    )

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2  # noqa: PLR2004


@override_settings(MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS=None)
async def test_history_without_params_returns_empty_list_without_rates(
    dmr_async_client: DMRAsyncClient,
    fiat_currency: FiatCurrency,
) -> None:
    response = await dmr_async_client.get(
        f"/api/fiat/rates/{fiat_currency.iso_code}/history",
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []
