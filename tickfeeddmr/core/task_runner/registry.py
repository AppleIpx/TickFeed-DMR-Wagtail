from __future__ import annotations

from typing import Any

import msgspec

from tickfeeddmr.market_data import tasks
from tickfeeddmr.market_data.models import CryptoAsset, FiatCurrency, StockAsset


class TaskSpec(msgspec.Struct, frozen=True):
    """Описание задачи для страницы ручного запуска."""

    task: Any
    title: str
    description: str
    asset_model: type | None = None
    takes_lock: bool = False


TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        task=tasks.poll_moex_board,
        title="Опрос борда MOEX",
        description="Снимок цены борда по всем активным акциям.",
        takes_lock=True,
    ),
    TaskSpec(
        task=tasks.poll_moex_trades,
        title="Опрос ленты сделок MOEX",
        description="Дочитывание ленты сделок для бумаг с `track_trades`.",
        takes_lock=True,
    ),
    TaskSpec(
        task=tasks.poll_cbr_rates,
        title="Опрос курсов ЦБ",
        description="Снимок ежедневного курса ЦБ РФ по активным валютам.",
        takes_lock=True,
    ),
    TaskSpec(
        task=tasks.catch_up_all_crypto_daily_candles,
        title="Догон дневных свечей крипты",
        description="Догрузка свечей по активным криптоактивам, до лимита за прогон.",
        takes_lock=True,
    ),
    TaskSpec(
        task=tasks.catch_up_all_stock_daily_candles,
        title="Догон дневных свечей акций",
        description="Догрузка свечей по активным акциям, до лимита за прогон.",
        takes_lock=True,
    ),
    TaskSpec(
        task=tasks.catch_up_all_fiat_daily_candles,
        title="Догон истории курсов",
        description="Догрузка истории курсов по активным валютам, до лимита за прогон.",
        takes_lock=True,
    ),
    TaskSpec(
        task=tasks.catch_up_crypto_asset_history,
        title="Догон истории одного криптоактива",
        description="Догрузка дневных свечей выбранного криптоактива.",
        asset_model=CryptoAsset,
    ),
    TaskSpec(
        task=tasks.catch_up_stock_asset_history,
        title="Догон истории одной акции",
        description="Догрузка дневных свечей выбранной акции.",
        asset_model=StockAsset,
    ),
    TaskSpec(
        task=tasks.catch_up_fiat_asset_history,
        title="Догон истории одной валюты",
        description="Догрузка истории курса выбранной валюты.",
        asset_model=FiatCurrency,
    ),
)

SPECS_BY_NAME: dict[str, TaskSpec] = {spec.task.name: spec for spec in TASKS}
