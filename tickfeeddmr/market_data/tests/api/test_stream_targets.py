from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.services.queries import crypto as crypto_queries
from tickfeeddmr.market_data.services.queries import stock as stock_queries
from tickfeeddmr.market_data.services.queries.errors import StreamAssetsNotFoundError
from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    StockAssetFactory,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import CryptoAsset, StockAsset

pytestmark = pytest.mark.django_db(transaction=True)


async def test_crypto_none_symbols_returns_only_active_binance_assets(
    crypto_asset: CryptoAsset,
) -> None:
    await sync_to_async(CryptoAssetFactory.create)(is_active=False)
    await sync_to_async(CryptoAssetFactory.create)(exchange="KRAKEN")

    targets = await crypto_queries.resolve_stream_targets(None)

    assert targets.symbols_by_stream_key == {
        crypto_asset.trading_pair: crypto_asset.symbol,
    }
    assert targets.unknown == []


async def test_crypto_partial_symbols_splits_found_and_unknown(
    crypto_asset: CryptoAsset,
) -> None:
    targets = await crypto_queries.resolve_stream_targets(
        [crypto_asset.symbol, "NOPE"],
    )

    assert targets.symbols_by_stream_key == {
        crypto_asset.trading_pair: crypto_asset.symbol,
    }
    assert targets.unknown == ["NOPE"]


async def test_crypto_inactive_asset_counts_as_unknown(
    crypto_asset: CryptoAsset,
) -> None:
    inactive = await sync_to_async(CryptoAssetFactory.create)(is_active=False)

    targets = await crypto_queries.resolve_stream_targets(
        [crypto_asset.symbol, inactive.symbol],
    )

    assert targets.unknown == [inactive.symbol]


async def test_crypto_no_filter_and_nothing_active_raises_generic_message() -> None:
    with pytest.raises(StreamAssetsNotFoundError) as exc_info:
        await crypto_queries.resolve_stream_targets(None)

    assert "Нет активных крипто-активов" in str(exc_info.value)


async def test_crypto_explicit_symbols_none_found_raises_with_requested_list() -> None:
    with pytest.raises(StreamAssetsNotFoundError) as exc_info:
        await crypto_queries.resolve_stream_targets(["NOPE1", "NOPE2"])

    message = str(exc_info.value)
    assert "NOPE1" in message
    assert "NOPE2" in message
    assert "Ни один из запрошенных тикеров" in message


# --- Акции -----------------------------------------------------------------


async def test_stock_none_secids_returns_only_active_track_trades_assets() -> None:
    tracked = await sync_to_async(StockAssetFactory.create)(track_trades=True)
    await sync_to_async(StockAssetFactory.create)(track_trades=False)
    await sync_to_async(StockAssetFactory.create)(track_trades=True, is_active=False)

    targets = await stock_queries.resolve_stream_targets(None)

    assert targets.symbols_by_stream_key == {tracked.symbol: tracked.symbol}
    assert targets.unknown == []


async def test_stock_partial_secids_splits_found_and_unknown() -> None:
    tracked = await sync_to_async(StockAssetFactory.create)(track_trades=True)

    targets = await stock_queries.resolve_stream_targets([tracked.symbol, "NOPE"])

    assert targets.symbols_by_stream_key == {tracked.symbol: tracked.symbol}
    assert targets.unknown == ["NOPE"]


async def test_stock_asset_without_track_trades_counts_as_unknown() -> None:
    tracked = await sync_to_async(StockAssetFactory.create)(track_trades=True)
    no_trades: StockAsset = await sync_to_async(StockAssetFactory.create)(
        track_trades=False,
    )

    targets = await stock_queries.resolve_stream_targets(
        [tracked.symbol, no_trades.symbol],
    )

    assert targets.unknown == [no_trades.symbol]


async def test_stock_no_filter_and_nothing_active_raises_generic_message() -> None:
    with pytest.raises(StreamAssetsNotFoundError) as exc_info:
        await stock_queries.resolve_stream_targets(None)

    assert "Нет бумаг с включённой лентой" in str(exc_info.value)


async def test_stock_explicit_secids_none_found_raises_with_requested_list() -> None:
    with pytest.raises(StreamAssetsNotFoundError) as exc_info:
        await stock_queries.resolve_stream_targets(["NOPE1", "NOPE2"])

    message = str(exc_info.value)
    assert "NOPE1" in message
    assert "NOPE2" in message
    assert "Ни одна из запрошенных бумаг" in message
