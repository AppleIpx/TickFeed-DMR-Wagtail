"""Сервисы записи данных MOEX ISS: снимок борда и лента сделок.

Зеркалит `services/ingest.py::CryptoTradeIngestService` по духу (резолв
актива, `bulk_create`, лог о необслуженных строках), но отличается в двух
местах:

- источник — `MoexBoardRow`/`MoexTradeRow` из `providers/moex/types.py`,
  не `TradeEvent` (см. докстринг `MoexTradeRow` про поле `period`,
  которое `TradeEvent` не несёт);
- идемпотентность обеспечена на уровне БД: `StockPriceSnapshot`/
  `StockTrade` несут `UniqueConstraint`, поэтому запись —
  `bulk_create(..., ignore_conflicts=True)`, а не голый `bulk_create`
  как у `CryptoPriceSnapshot` (там такого ограничения пока нет).
"""

import logging
from typing import TYPE_CHECKING

import msgspec

from tickfeeddmr.market_data.models import StockAsset, StockPriceSnapshot, StockTrade

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.providers.moex.types import MoexBoardRow, MoexTradeRow

logger = logging.getLogger(__name__)


class BoardSnapshotWriteResult(msgspec.Struct, frozen=True):
    """Итог записи снимка борда — сырые счётчики для лога вызывающей задачи."""

    written: int
    skipped_not_trading: int
    skipped_unknown_asset: int


class MoexBoardSnapshotService:
    """Резолвит `StockAsset` по `(board, symbol)` и пишет `StockPriceSnapshot`."""

    def __init__(self, *, board: str) -> None:
        self._board = board

    async def write_snapshots(
        self,
        rows: Sequence[MoexBoardRow],
    ) -> BoardSnapshotWriteResult:
        """Записать `rows`, вернуть счётчики для лога вызывающей задачи.

        Пишет только по бумагам с `is_active=True` — снимок ISS покрывает
        весь борд (порядка 500 бумаг), а в БД собираем только то, что
        реально отслеживается. Строки с `TRADINGSTATUS`, отличным от
        "торги идут" (`MoexBoardRow.is_trading`), не пишутся вовсе — вне
        сессии данные не обновляются, писать в этот момент нечего (см.
        докстринг `market_data/tasks.py::poll_moex_board`).

        Точное число отброшенных `bulk_create` дубликатов по
        `UniqueConstraint(asset, timestamp)` ORM не возвращает при
        `ignore_conflicts=True` (Django не проставляет pk пропущенным
        строкам, отличить их от вставленных без отдельного `COUNT`
        нельзя) — осознанное упрощение этапа 4, число подготовленных к
        записи строк (`written`) не равно числу реально вставленных при
        повторном прогоне с тем же `timestamp`.
        """
        if not rows:
            return BoardSnapshotWriteResult(0, 0, 0)

        secids = {row.secid for row in rows}
        assets_by_secid = {
            asset.symbol: asset
            async for asset in StockAsset.objects.filter(
                board=self._board,
                symbol__in=secids,
                is_active=True,
            )
        }

        snapshots = []
        skipped_not_trading = 0
        skipped_unknown_asset = 0
        for row in rows:
            asset = assets_by_secid.get(row.secid)
            if asset is None:
                skipped_unknown_asset += 1
                continue
            if not row.is_trading:
                skipped_not_trading += 1
                continue
            snapshots.append(
                StockPriceSnapshot(
                    asset=asset,
                    last=row.last,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    change=row.change,
                    change_percent=row.change_percent,
                    volume=row.volume,
                    value=row.value,
                    num_trades=row.num_trades,
                    timestamp=row.timestamp,
                ),
            )

        if snapshots:
            await StockPriceSnapshot.objects.abulk_create(
                snapshots,
                ignore_conflicts=True,
            )
        return BoardSnapshotWriteResult(
            written=len(snapshots),
            skipped_not_trading=skipped_not_trading,
            skipped_unknown_asset=skipped_unknown_asset,
        )


class MoexTradeIngestService:
    """Пишет `StockTrade` по одной бумаге из дочитанных `MoexTradeRow`."""

    async def write_trades(
        self,
        asset: StockAsset,
        rows: Sequence[MoexTradeRow],
    ) -> int:
        """Записать `rows` как `StockTrade`, вернуть число подготовленных строк.

        Курсор (`StockAsset.last_trade_no`) не трогает — сдвигать его
        после успешной записи решает вызывающая задача
        (`poll_moex_trades`), по аналогии с тем как
        `consume_market_data_stream` сам решает, когда `XACK`нуть.
        """
        if not rows:
            return 0
        trades = [
            StockTrade(
                asset=asset,
                trade_id=row.trade_id,
                price=row.price,
                quantity=row.quantity,
                side=row.side,
                period=row.period,
                timestamp=row.timestamp,
            )
            for row in rows
        ]
        await StockTrade.objects.abulk_create(trades, ignore_conflicts=True)
        return len(trades)
