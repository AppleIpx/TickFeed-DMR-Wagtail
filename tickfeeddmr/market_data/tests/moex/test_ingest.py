"""Юнит-тесты `MoexBoardSnapshotService`/`MoexTradeIngestService`.

Требует реальную БД (не sqlite), как и `binance/test_ingest.py` — гоняется
через `just pytest` / `pytest --ds=config.settings.test` с поднятым
Postgres и применённой миграцией для `StockAsset`/`StockPriceSnapshot`/
`StockTrade`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from tickfeeddmr.market_data.models import StockPriceSnapshot, StockTrade
from tickfeeddmr.market_data.providers.moex.types import MoexBoardRow, MoexTradeRow
from tickfeeddmr.market_data.services.moex_ingest import (
    MoexBoardSnapshotService,
    MoexTradeIngestService,
)

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import StockAsset

pytestmark = pytest.mark.django_db(transaction=True)

TIMESTAMP = datetime(2026, 9, 8, 9, 44, 28, tzinfo=UTC)
TRADE_ID = 1001


def _board_row(
    secid: str,
    *,
    trading_status: str = "T",
    timestamp: datetime = TIMESTAMP,
) -> MoexBoardRow:
    return MoexBoardRow(
        secid=secid,
        last=Decimal("250.55"),
        open=Decimal("248.10"),
        high=Decimal("252.30"),
        low=Decimal("247.00"),
        change=Decimal("2.45"),
        change_percent=Decimal("0.98"),
        volume=123_456,
        value=Decimal("30000000.00"),
        num_trades=4200,
        timestamp=timestamp,
        trading_status=trading_status,
    )


def _trade_row(trade_id: int, *, period: str = "N") -> MoexTradeRow:
    return MoexTradeRow(
        trade_id=trade_id,
        price=Decimal("250.55"),
        quantity=10,
        side="buy",
        timestamp=TIMESTAMP,
        period=period,
    )


async def test_write_snapshots_resolves_known_asset_and_writes(
    stock_asset: StockAsset,
) -> None:
    service = MoexBoardSnapshotService(board=stock_asset.board)
    row = _board_row(stock_asset.symbol)

    result = await service.write_snapshots([row])

    assert result.written == 1
    assert result.skipped_not_trading == 0
    assert result.skipped_unknown_asset == 0
    snapshot = await StockPriceSnapshot.objects.aget()
    assert snapshot.asset_id == stock_asset.id
    assert snapshot.last == row.last
    assert snapshot.timestamp == row.timestamp


async def test_write_snapshots_is_idempotent_on_rerun(stock_asset: StockAsset) -> None:
    service = MoexBoardSnapshotService(board=stock_asset.board)
    row = _board_row(stock_asset.symbol)

    await service.write_snapshots([row])
    await service.write_snapshots([row])  # тот же timestamp -> должен быть отброшен БД

    assert await StockPriceSnapshot.objects.acount() == 1


async def test_write_snapshots_skips_rows_when_trading_closed(
    stock_asset: StockAsset,
) -> None:
    service = MoexBoardSnapshotService(board=stock_asset.board)
    row = _board_row(stock_asset.symbol, trading_status="C")

    result = await service.write_snapshots([row])

    assert result.written == 0
    assert result.skipped_not_trading == 1
    assert not await StockPriceSnapshot.objects.aexists()


async def test_write_snapshots_skips_unknown_secid(stock_asset: StockAsset) -> None:
    service = MoexBoardSnapshotService(board=stock_asset.board)
    row = _board_row("UNKNOWNSECID")

    result = await service.write_snapshots([row])

    assert result.written == 0
    assert result.skipped_unknown_asset == 1
    assert not await StockPriceSnapshot.objects.aexists()


async def test_write_snapshots_skips_inactive_asset(stock_asset: StockAsset) -> None:
    stock_asset.is_active = False
    await stock_asset.asave(update_fields=["is_active"])
    service = MoexBoardSnapshotService(board=stock_asset.board)
    row = _board_row(stock_asset.symbol)

    result = await service.write_snapshots([row])

    assert result.written == 0
    assert result.skipped_unknown_asset == 1


async def test_write_snapshots_empty_list_returns_zero_without_querying() -> None:
    result = await MoexBoardSnapshotService(board="TQBR").write_snapshots([])

    assert result.written == 0
    assert result.skipped_not_trading == 0
    assert result.skipped_unknown_asset == 0


async def test_write_trades_writes_rows(stock_asset: StockAsset) -> None:
    service = MoexTradeIngestService()
    row = _trade_row(TRADE_ID)

    written = await service.write_trades(stock_asset, [row])

    assert written == 1
    trade = await StockTrade.objects.aget()
    assert trade.asset_id == stock_asset.id
    assert trade.trade_id == TRADE_ID
    assert trade.period == "N"


async def test_write_trades_is_idempotent_on_rerun(stock_asset: StockAsset) -> None:
    service = MoexTradeIngestService()
    row = _trade_row(TRADE_ID)

    await service.write_trades(stock_asset, [row])
    await service.write_trades(stock_asset, [row])  # тот же trade_id -> дубль отброшен

    assert await StockTrade.objects.filter(asset=stock_asset).acount() == 1


async def test_write_trades_empty_list_returns_zero_without_querying(
    stock_asset: StockAsset,
) -> None:
    written = await MoexTradeIngestService().write_trades(stock_asset, [])

    assert written == 0
    assert not await StockTrade.objects.aexists()
