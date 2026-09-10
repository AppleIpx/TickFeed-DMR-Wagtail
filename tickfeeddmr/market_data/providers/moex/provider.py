import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING

from tickfeeddmr.market_data.providers.base import (
    AssetDataProvider,
    PricePoint,
    TradeEvent,
)
from tickfeeddmr.market_data.providers.exceptions import ProviderResponseError
from tickfeeddmr.market_data.providers.moex.client import MoexIssClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from datetime import datetime

    from tickfeeddmr.market_data.providers.moex.types import MoexBoardRow, MoexTradeRow

EXCHANGE = "MOEX"

# Числовой код интервала свечей ISS ("1" = 1 минута), не строка формата
# Binance ("1m") — форматы интервалов у провайдеров разные по контракту
# `AssetDataProvider.fetch_history` (см. её докстринг в `providers/base.py`).
DEFAULT_CANDLE_INTERVAL = "1"

# Интервал поллинга внутри `stream()` — только для соответствия ABC, см.
# докстринг класса; текущие Celery-задачи этапа 4 этот метод не вызывают.
TRADES_POLL_INTERVAL_SECONDS = 5.0


class MoexProvider(AssetDataProvider):
    """Реализация `AssetDataProvider` поверх ISS MOEX.

    В отличие от `BinanceProvider`, у акций MOEX нет push-канала сделок —
    `stream()` реализован поллингом `MoexIssClient.get_trades_page` и
    существует для соответствия ABC и на случай будущего generic-
    потребителя `TradeEvent`. Реальный сбор ленты сделок для записи в БД
    (этап 4, `market_data/tasks.py::poll_moex_trades`) в этот метод не
    ходит: `TradeEvent` не несёт поле `period`, нужное для решения по
    аукционным сделкам (см. `MoexTradeRow`), поэтому задача работает с
    `MoexIssClient`/`MoexTradeIngestService` напрямую через
    `get_trades_page`, минуя `stream()`.

    Каждый запрос к ISS повторяется внутри `MoexIssClient` при сетевых
    сбоях и статусах 429/500/502/503/504; после исчерпания попыток методы
    поднимают `ProviderConnectionError`. Общего бюджета на несколько
    запросов здесь нет — `fetch_history`/`stream()` делают их серию, и
    вызывающий код, которому нужен потолок по времени, ставит свой
    `asyncio.timeout`; если он оборвёт запрос, причину последней неудачной
    попытки можно взять из `last_failure_reason`.
    """

    def __init__(
        self,
        *,
        base_url: str,
        default_board: str,
        client: MoexIssClient | None = None,
    ) -> None:
        self._default_board = default_board
        self._client = client or MoexIssClient(base_url=base_url)

    @property
    def last_failure_reason(self) -> str | None:
        """Проброс `MoexIssClient.last_failure_reason` — для лога по бюджету прогона."""
        return self._client.last_failure_reason

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_board_snapshot(self, board: str) -> Sequence[MoexBoardRow]:
        """Проброс к клиенту — используется `poll_moex_board` напрямую."""
        return await self._client.get_board_snapshot(board)

    async def get_trades_page(
        self,
        secid: str,
        *,
        since_trade_no: int | None = None,
    ) -> Sequence[MoexTradeRow]:
        """Проброс к клиенту — используется `poll_moex_trades` напрямую."""
        return await self._client.get_trades_page(secid, since_trade_no=since_trade_no)

    async def fetch_current(self, trading_pair: str) -> PricePoint:
        """Текущая цена одной бумаги — через снимок борда по умолчанию.

        Не оптимизировано под одиночные вызовы (тянет весь борд и
        фильтрует по `SECID`), но это не hot path этапа 4 —
        `poll_moex_board` ходит в `get_board_snapshot` напрямую и этот
        метод не вызывает. Сделано так, чтобы не заводить отдельный,
        отдельно не проверенный вживую ISS-эндпоинт под единственный
        сценарий использования (соответствие ABC).
        """
        rows = await self._client.get_board_snapshot(self._default_board)
        for row in rows:
            if row.secid != trading_pair:
                continue
            if row.last is None:
                msg = f"MOEX board snapshot has no LAST price for {trading_pair}"
                raise ProviderResponseError(msg)
            return PricePoint(
                trading_pair=trading_pair,
                price=row.last,
                volume=Decimal(row.volume) if row.volume is not None else None,
                timestamp=row.timestamp,
            )
        msg = f"{trading_pair} not found on board {self._default_board}"
        raise ProviderResponseError(msg)

    async def fetch_history(
        self,
        trading_pair: str,
        *,
        start: datetime,
        end: datetime | None = None,
        interval: str = DEFAULT_CANDLE_INTERVAL,
    ) -> AsyncIterator[PricePoint]:
        cursor = start
        while True:
            batch = await self._client.get_candles(
                trading_pair,
                start=cursor,
                end=end,
                interval=interval,
            )
            if not batch:
                return
            for candle in batch:
                yield PricePoint(
                    trading_pair=trading_pair,
                    price=candle.close,
                    volume=Decimal(candle.volume),
                    timestamp=candle.end,
                )
            cursor = batch[-1].end
            if end is not None and cursor >= end:
                return

    async def stream(self, trading_pairs: Sequence[str]) -> AsyncIterator[TradeEvent]:
        """Поллинг-эмуляция потока сделок — только для соответствия ABC.

        См. докстринг класса: этап 4 не использует этот метод для записи
        в БД. Курсоры пар живут только в рамках одного вызова генератора и
        не персистятся — персистентный курсор (`StockAsset.last_trade_no`)
        обслуживает `poll_moex_trades`, не этот метод.
        """
        cursors: dict[str, int | None] = dict.fromkeys(trading_pairs)
        while True:
            for pair in trading_pairs:
                rows = await self._client.get_trades_page(
                    pair,
                    since_trade_no=cursors[pair],
                )
                for row in rows:
                    yield TradeEvent(
                        trading_pair=pair,
                        price=row.price,
                        volume=Decimal(row.quantity),
                        side=row.side,
                        timestamp=row.timestamp,
                        trade_id=str(row.trade_id),
                    )
                if rows:
                    cursors[pair] = rows[-1].trade_id
            await asyncio.sleep(TRADES_POLL_INTERVAL_SECONDS)
