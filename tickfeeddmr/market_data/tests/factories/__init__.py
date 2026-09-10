"""Фабрики `factory_boy` для моделей `market_data`, по одному файлу на источник данных.

По образцу `market_data/models/`: `crypto.py`/`fiat.py`/`stock.py` вместо
одного плоского `factories.py`. Реэкспорт здесь нужен, чтобы существующие
импорты (`from tickfeeddmr.market_data.tests.factories import ...` в
`conftest_plugins/market_data_fixtures.py`) остались рабочими без изменений.
"""

from tickfeeddmr.market_data.tests.factories.crypto import (
    CryptoAssetFactory,
    CryptoPriceSnapshotFactory,
)
from tickfeeddmr.market_data.tests.factories.fiat import (
    FiatCurrencyFactory,
    FiatPriceSnapshotFactory,
)
from tickfeeddmr.market_data.tests.factories.stock import (
    StockAssetFactory,
    StockPriceSnapshotFactory,
    StockTradeFactory,
)

__all__ = [
    "CryptoAssetFactory",
    "CryptoPriceSnapshotFactory",
    "FiatCurrencyFactory",
    "FiatPriceSnapshotFactory",
    "StockAssetFactory",
    "StockPriceSnapshotFactory",
    "StockTradeFactory",
]
