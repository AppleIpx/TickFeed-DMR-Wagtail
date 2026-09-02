"""Юнит-тесты `CryptoTradeIngestService.write_snapshots`.

Требует реальную БД (не sqlite) — как и остальные тесты моделей в
проекте, гоняется через `just pytest` / `pytest --ds=config.settings.test`
с поднятым Postgres, см. `crypto_asset` в
`tickfeeddmr/conftest_plugins/market_data_fixtures.py`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from tickfeeddmr.market_data.models import CryptoPriceSnapshot
from tickfeeddmr.market_data.providers.base import TradeEvent
from tickfeeddmr.market_data.services.ingest import CryptoTradeIngestService

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = pytest.mark.django_db(transaction=True)


def _event(trading_pair: str, *, trade_id: str) -> TradeEvent:
    return TradeEvent(
        trading_pair=trading_pair,
        price=Decimal("100.5"),
        volume=Decimal("2"),
        side="buy",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        trade_id=trade_id,
    )


async def test_write_snapshots_resolves_known_pair_and_bulk_creates(
    crypto_asset: CryptoAsset,
) -> None:
    service = CryptoTradeIngestService(exchange=crypto_asset.exchange)
    event = _event(crypto_asset.trading_pair, trade_id="1")

    written = await service.write_snapshots([event])

    assert written == 1
    snapshot = await CryptoPriceSnapshot.objects.aget()
    assert snapshot.asset_id == crypto_asset.id
    assert snapshot.price == event.price
    assert snapshot.volume == event.volume
    assert snapshot.timestamp == event.timestamp


async def test_write_snapshots_skips_unknown_trading_pair(
    crypto_asset: CryptoAsset,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = CryptoTradeIngestService(exchange=crypto_asset.exchange)
    event = _event("UNKNOWNPAIR", trade_id="1")

    with caplog.at_level(logging.ERROR):
        written = await service.write_snapshots([event])

    assert written == 0
    assert not await CryptoPriceSnapshot.objects.aexists()
    assert any("UNKNOWNPAIR" in record.message for record in caplog.records)


async def test_write_snapshots_persists_only_known_pairs_from_mixed_batch(
    crypto_asset: CryptoAsset,
) -> None:
    service = CryptoTradeIngestService(exchange=crypto_asset.exchange)
    events = [
        _event(crypto_asset.trading_pair, trade_id="1"),
        _event("UNKNOWNPAIR", trade_id="2"),
    ]

    written = await service.write_snapshots(events)

    assert written == 1
    assert await CryptoPriceSnapshot.objects.acount() == 1


async def test_write_snapshots_scopes_resolution_by_exchange(
    crypto_asset: CryptoAsset,
) -> None:
    # trading_pair существует, но у другой биржи -> для этого exchange он неизвестен.
    other_exchange = "OTHER_EXCHANGE"
    assert crypto_asset.exchange != other_exchange
    service = CryptoTradeIngestService(exchange=other_exchange)
    event = _event(crypto_asset.trading_pair, trade_id="1")

    written = await service.write_snapshots([event])

    assert written == 0
    assert not await CryptoPriceSnapshot.objects.aexists()


async def test_write_snapshots_empty_list_returns_zero_without_querying() -> None:
    written = await CryptoTradeIngestService(exchange="BINANCE").write_snapshots([])

    assert written == 0
