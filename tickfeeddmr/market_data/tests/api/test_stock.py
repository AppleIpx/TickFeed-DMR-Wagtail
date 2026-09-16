from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.tests.factories import (
    StockAssetFactory,
    StockTradeFactory,
)

if TYPE_CHECKING:
    from dmr.test import DMRAsyncClient

    from tickfeeddmr.market_data.models import StockAsset, StockPriceSnapshot

pytestmark = pytest.mark.django_db(transaction=True)


async def test_list_assets_returns_only_active_assets(
    dmr_async_client: DMRAsyncClient,
    stock_asset: StockAsset,
) -> None:
    await sync_to_async(StockAssetFactory.create)(is_active=False)

    response = await dmr_async_client.get("/api/stocks/")

    assert response.status_code == HTTPStatus.OK
    symbols = [item["symbol"] for item in response.json()]
    assert symbols == [stock_asset.symbol]


async def test_current_returns_board_snapshot_with_string_and_int_fields(
    dmr_async_client: DMRAsyncClient,
    stock_asset: StockAsset,
    stock_price_snapshot: StockPriceSnapshot,
) -> None:
    response = await dmr_async_client.get(
        f"/api/stocks/{stock_asset.symbol}/current",
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["asset"]["symbol"] == stock_asset.symbol
    assert isinstance(body["last"], str)
    assert isinstance(body["volume"], int)
    assert isinstance(body["num_trades"], int)


async def test_current_unknown_secid_returns_404_asset_not_found(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/stocks/UNKNOWN/current")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "не найдена" in response.json()["detail"][0]["msg"]


async def test_current_active_asset_without_snapshot_returns_404_no_data_yet(
    dmr_async_client: DMRAsyncClient,
    stock_asset: StockAsset,
) -> None:
    response = await dmr_async_client.get(
        f"/api/stocks/{stock_asset.symbol}/current",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "ещё нет данных" in response.json()["detail"][0]["msg"]


async def test_trades_unknown_secid_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/stocks/UNKNOWN/trades")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_trades_not_tracked_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    asset = await sync_to_async(StockAssetFactory.create)(track_trades=False)

    response = await dmr_async_client.get(f"/api/stocks/{asset.symbol}/trades")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "не ведётся" in response.json()["detail"][0]["msg"]


async def test_trades_tracked_and_empty_returns_200_with_empty_items(
    dmr_async_client: DMRAsyncClient,
) -> None:
    asset = await sync_to_async(StockAssetFactory.create)(track_trades=True)

    response = await dmr_async_client.get(f"/api/stocks/{asset.symbol}/trades")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


async def test_trades_returns_period_as_raw_value(
    dmr_async_client: DMRAsyncClient,
) -> None:
    asset = await sync_to_async(StockAssetFactory.create)(track_trades=True)
    trade = await sync_to_async(StockTradeFactory.create)(asset=asset, period="N")

    response = await dmr_async_client.get(f"/api/stocks/{asset.symbol}/trades")

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["period"] == "N"
    assert body["items"][0]["trade_id"] == trade.trade_id
