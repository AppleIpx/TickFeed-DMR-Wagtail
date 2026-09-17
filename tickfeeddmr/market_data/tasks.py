import asyncio

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from tickfeeddmr.market_data.models import CryptoAsset, FiatCurrency, StockAsset
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.cbr_polling import poll_rates
from tickfeeddmr.market_data.services.cbr_polling.errors import (
    CbrPollBudgetExceededError,
)
from tickfeeddmr.market_data.services.daily_candles import (
    crypto as crypto_daily_candles,
)
from tickfeeddmr.market_data.services.daily_candles import fiat as fiat_daily_candles
from tickfeeddmr.market_data.services.daily_candles import stock as stock_daily_candles
from tickfeeddmr.market_data.services.moex_polling import poll_board, poll_trades
from tickfeeddmr.market_data.services.moex_polling.errors import (
    PollBudgetExceededError,
)

logger = get_task_logger(__name__)

EXPECTED_POLL_FAILURES = (ProviderConnectionError, PollBudgetExceededError)
EXPECTED_CBR_POLL_FAILURES = (ProviderConnectionError, CbrPollBudgetExceededError)

# Повторы сигнального (одноактивного) догона — транзитная недоступность
# источника в момент создания актива в админке не должна оставлять актив
# без истории до следующей ночи: несколько попыток с задержкой обычно
# решают вопрос сразу. Ночная задача повторов на уровне Celery не
# использует — недогруженное просто продолжится следующей ночью
# (см. `services/daily_candles/budget.py`).
_ASSET_CATCH_UP_MAX_RETRIES = 5


@shared_task(throws=EXPECTED_POLL_FAILURES)
def poll_moex_board() -> None:
    """Снимок цены борда MOEX по всем активным `StockAsset` этого борда."""
    asyncio.run(poll_board())


@shared_task(throws=EXPECTED_POLL_FAILURES)
def poll_moex_trades() -> None:
    """Дочитывание ленты сделок MOEX для бумаг с `track_trades=True`."""
    asyncio.run(poll_trades())


@shared_task(throws=EXPECTED_CBR_POLL_FAILURES)
def poll_cbr_rates() -> None:
    """Снимок ежедневного курса ЦБ РФ по всем активным `FiatCurrency`."""
    asyncio.run(poll_rates())


@shared_task(
    bind=True,
    autoretry_for=(ProviderConnectionError,),
    retry_backoff=True,
    max_retries=_ASSET_CATCH_UP_MAX_RETRIES,
)
def catch_up_crypto_asset_history(self, asset_id: int) -> None:
    """Догрузить дневные свечи одного нового `CryptoAsset` (сигнал `post_save`)."""
    asyncio.run(_catch_up_crypto_asset(asset_id))


async def _catch_up_crypto_asset(asset_id: int) -> None:
    asset = await CryptoAsset.objects.aget(pk=asset_id)
    result = await crypto_daily_candles.catch_up_asset(asset)
    logger.info(
        f"Сигнальный догон дневных свечей крипты {asset.symbol}: "
        f"записано {result.written}, уже актуально: {result.already_up_to_date}",
    )


@shared_task
def catch_up_all_crypto_daily_candles() -> None:
    """Ночной догон дневных свечей по всем активным `CryptoAsset`."""
    asyncio.run(
        crypto_daily_candles.catch_up_all_assets(
            limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
        ),
    )


@shared_task(
    bind=True,
    autoretry_for=(ProviderConnectionError,),
    retry_backoff=True,
    max_retries=_ASSET_CATCH_UP_MAX_RETRIES,
)
def catch_up_stock_asset_history(self, asset_id: int) -> None:
    """Догрузить дневные свечи одной новой `StockAsset` (сигнал `post_save`)."""
    asyncio.run(_catch_up_stock_asset(asset_id))


async def _catch_up_stock_asset(asset_id: int) -> None:
    asset = await StockAsset.objects.aget(pk=asset_id)
    result = await stock_daily_candles.catch_up_asset(asset)
    logger.info(
        f"Сигнальный догон дневных свечей акции {asset.symbol}: "
        f"записано {result.written}, уже актуально: {result.already_up_to_date}",
    )


@shared_task
def catch_up_all_stock_daily_candles() -> None:
    """Ночной догон дневных свечей по всем активным `StockAsset`."""
    asyncio.run(
        stock_daily_candles.catch_up_all_assets(
            limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
        ),
    )


@shared_task(
    bind=True,
    autoretry_for=(ProviderConnectionError,),
    retry_backoff=True,
    max_retries=_ASSET_CATCH_UP_MAX_RETRIES,
)
def catch_up_fiat_asset_history(self, asset_id: int) -> None:
    """Догрузить историю курса одной новой `FiatCurrency` (сигнал `post_save`)."""
    asyncio.run(_catch_up_fiat_asset(asset_id))


async def _catch_up_fiat_asset(asset_id: int) -> None:
    asset = await FiatCurrency.objects.aget(pk=asset_id)
    result = await fiat_daily_candles.catch_up_asset(asset)
    logger.info(
        f"Сигнальный догон истории курса {asset.symbol}: "
        f"записано {result.written}, уже актуально: {result.already_up_to_date}",
    )


@shared_task
def catch_up_all_fiat_daily_candles() -> None:
    """Ночной догон истории курсов по всем активным `FiatCurrency`."""
    asyncio.run(
        fiat_daily_candles.catch_up_all_assets(
            limit=settings.MARKET_DATA_DAILY_CANDLES_MAX_ASSETS_PER_RUN,
        ),
    )
