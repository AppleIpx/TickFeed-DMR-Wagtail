from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    CryptoDailyCandleFactory,
    CryptoPriceSnapshotFactory,
)

if TYPE_CHECKING:
    from dmr.test import DMRAsyncClient

    from tickfeeddmr.market_data.models import CryptoAsset, CryptoPriceSnapshot

pytestmark = pytest.mark.django_db(transaction=True)


async def test_list_assets_returns_only_active_assets(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    await sync_to_async(CryptoAssetFactory.create)(is_active=False)

    response = await dmr_async_client.get("/api/crypto/assets/")

    assert response.status_code == HTTPStatus.OK
    symbols = [item["symbol"] for item in response.json()]
    assert symbols == [crypto_asset.symbol]


async def test_current_returns_price_as_string_not_float(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
    crypto_price_snapshot: CryptoPriceSnapshot,
) -> None:
    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/current",
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["asset"]["symbol"] == crypto_asset.symbol
    assert isinstance(body["price"], str)
    assert Decimal(body["price"]) == crypto_price_snapshot.price
    assert isinstance(body["volume"], str)
    assert "freshness" in body


async def test_current_unknown_symbol_returns_404_asset_not_found(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/crypto/assets/UNKNOWN/current")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "не найден" in response.json()["detail"][0]["msg"]


async def test_current_active_asset_without_snapshot_returns_404_no_data_yet(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/current",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "ещё нет данных" in response.json()["detail"][0]["msg"]


async def test_trades_unknown_symbol_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/crypto/assets/UNKNOWN/trades")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "не найден" in response.json()["detail"][0]["msg"]


async def test_trades_empty_feed_returns_200_with_empty_items(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/trades",
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body == {
        "items": [],
        "next_cursor": None,
        "freshness": body["freshness"],
    }


async def test_trades_excludes_legacy_rows_without_trade_id_and_side(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        trade_id=None,
        side=None,
    )
    tracked = await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        trade_id="42",
        side="buy",
    )

    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/trades",
    )

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["trade_id"] == "42"
    assert body["items"][0]["side"] == "buy"
    assert body["items"][0]["price"] == str(tracked.price)


async def test_trades_invalid_cursor_returns_422(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/trades?cursor=garbage",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["detail"][0]["msg"]


async def test_trades_pagination_next_cursor_reaches_remaining_page(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    older = await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        trade_id="1",
        side="buy",
        timestamp=base,
    )
    newer = await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        trade_id="2",
        side="sell",
        timestamp=base + timedelta(minutes=1),
    )

    first = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/trades?limit=1",
    )
    first_body = first.json()
    assert [item["trade_id"] for item in first_body["items"]] == [newer.trade_id]
    assert first_body["next_cursor"] is not None

    second = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/trades"
        f"?limit=1&cursor={first_body['next_cursor']}",
    )
    second_body = second.json()
    assert [item["trade_id"] for item in second_body["items"]] == [older.trade_id]
    assert second_body["next_cursor"] is None


async def test_intraday_unknown_symbol_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/crypto/assets/UNKNOWN/intraday")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_intraday_returns_aggregated_points(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    now = datetime.now(UTC)
    snapshot = await sync_to_async(CryptoPriceSnapshotFactory.create)(
        asset=crypto_asset,
        timestamp=now,
        price=Decimal("100"),
        volume=Decimal("1"),
    )

    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/intraday",
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body["points"]) == 1
    assert Decimal(body["points"][0]["price"]) == snapshot.price
    assert "freshness" in body


async def test_history_unknown_symbol_returns_404(
    dmr_async_client: DMRAsyncClient,
) -> None:
    response = await dmr_async_client.get("/api/crypto/assets/UNKNOWN/history")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_history_from_after_to_returns_422(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/history"
        "?from=2026-09-18&to=2026-01-01",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_history_returns_candles_as_strings_within_period(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    candle = await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=datetime(2026, 6, 1, tzinfo=UTC).date(),
    )
    await sync_to_async(CryptoDailyCandleFactory.create)(
        asset=crypto_asset,
        date=datetime(2020, 1, 1, tzinfo=UTC).date(),
    )

    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/history"
        "?from=2026-01-01&to=2026-12-31",
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["close"] == str(candle.close)
    assert isinstance(body[0]["volume"], str)
