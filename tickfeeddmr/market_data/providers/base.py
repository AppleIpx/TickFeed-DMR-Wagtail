from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from datetime import datetime
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PricePoint:
    """Одна точка цены актива — текущая котировка или свеча истории."""

    trading_pair: str
    price: Decimal
    volume: Decimal | None
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class TradeEvent:
    """Одна сделка, полученная из real-time стрима провайдера."""

    trading_pair: str
    price: Decimal
    volume: Decimal
    side: Literal["buy", "sell"]
    timestamp: datetime
    trade_id: str


class AssetDataProvider(ABC):
    """Общий интерфейс источника данных по одному активу.

    `trading_pair` — символ актива в нотации конкретного провайдера
    (например, `"BTCUSDT"` для Binance). Биржа не передаётся параметром —
    она зашита в конкретную реализацию (`BinanceProvider` умеет говорить
    только с Binance); выбор реализации под `CryptoAsset.exchange` остаётся
    на стороне вызывающего кода (management-команды).
    """

    @abstractmethod
    async def fetch_current(self, trading_pair: str) -> PricePoint:
        """Вернуть текущую цену актива одним запросом."""

    @abstractmethod
    def fetch_history(
        self,
        trading_pair: str,
        *,
        start: datetime,
        end: datetime | None = None,
        interval: str = "1m",
    ) -> AsyncIterator[PricePoint]:
        """Отдать историю цен за `[start, end)` по возрастанию времени.

        Реализация сама пагинирует запросы к источнику — вызывающий код
        получает единый поток `PricePoint`, не заботясь о лимитах API.
        `interval` — специфичная для провайдера строка (для Binance,
        например, `"1m"`/`"5m"`/`"1h"`).
        """

    @abstractmethod
    def stream(self, trading_pairs: Sequence[str]) -> AsyncIterator[TradeEvent]:
        """Отдать бесконечный поток сделок по перечисленным парам.

        Реализация держит одно постоянное соединение на все переданные
        пары и сама переподключается при обрыве — вызывающий код получает
        только уже нормализованные `TradeEvent`.
        """
