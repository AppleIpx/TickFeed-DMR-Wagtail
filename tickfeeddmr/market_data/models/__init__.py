"""Модели `market_data`, разложенные по источнику данных: `crypto`/`fiat`.

Django требует, чтобы при разбиении `models` на пакет все модели были
явно импортированы здесь — иначе классы в `crypto.py`/`fiat.py` не
попадут в реестр приложений и `makemigrations`/`migrate` их не увидят
(https://docs.djangoproject.com/en/stable/topics/db/models/#organizing-models-in-a-package).
"""

from tickfeeddmr.market_data.models.base import AssetBase
from tickfeeddmr.market_data.models.crypto import CryptoAsset, CryptoPriceSnapshot
from tickfeeddmr.market_data.models.fiat import (
    FiatCurrency,
    FiatPriceSnapshot,
    FiatSource,
)

__all__ = [
    "AssetBase",
    "CryptoAsset",
    "CryptoPriceSnapshot",
    "FiatCurrency",
    "FiatPriceSnapshot",
    "FiatSource",
]
