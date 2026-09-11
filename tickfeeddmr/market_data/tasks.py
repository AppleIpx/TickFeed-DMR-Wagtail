import asyncio

from celery import shared_task

from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.cbr_polling import poll_rates
from tickfeeddmr.market_data.services.cbr_polling.errors import (
    CbrPollBudgetExceededError,
)
from tickfeeddmr.market_data.services.moex_polling import poll_board, poll_trades
from tickfeeddmr.market_data.services.moex_polling.errors import (
    PollBudgetExceededError,
)

EXPECTED_POLL_FAILURES = (ProviderConnectionError, PollBudgetExceededError)
EXPECTED_CBR_POLL_FAILURES = (ProviderConnectionError, CbrPollBudgetExceededError)


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
