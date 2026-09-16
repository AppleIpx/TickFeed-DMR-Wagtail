from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.tests.factories import FiatCurrencyFactory

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
