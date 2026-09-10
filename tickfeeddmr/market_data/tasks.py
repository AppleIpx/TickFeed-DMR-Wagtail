"""Celery-задачи опроса ISS MOEX — тонкие обёртки над `services/moex_polling/`.

`throws=EXPECTED_POLL_FAILURES` — два ожидаемых исхода, а не баги:
`ProviderConnectionError` (ISS недоступен после повторов `MoexIssClient`)
и `PollBudgetExceededError` (прогон не уложился в свой бюджет времени —
не обязательно из-за ISS, поэтому отдельный класс). Тик получает статус
FAILURE (ошибка не прячется под успешное выполнение), но Celery логирует
его как "raised expected: <repr исключения>" на уровне INFO без трейса;
причину пуллер уже записал одной строкой WARNING. Голый `TimeoutError` в
`throws` сознательно не входит: бюджет пуллеры сами переводят в
`PollBudgetExceededError`, а посторонние таймауты (Redis, БД) должны
падать с полным трейсом, как и любые другие ошибки (4xx ISS, провал
проверки TLS-сертификата, парсинг, БД).
"""

import asyncio

from celery import shared_task

from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.moex_polling import poll_board, poll_trades
from tickfeeddmr.market_data.services.moex_polling.errors import (
    PollBudgetExceededError,
)

EXPECTED_POLL_FAILURES = (ProviderConnectionError, PollBudgetExceededError)


@shared_task(throws=EXPECTED_POLL_FAILURES)
def poll_moex_board() -> None:
    """Снимок цены борда MOEX по всем активным `StockAsset` этого борда."""
    asyncio.run(poll_board())


@shared_task(throws=EXPECTED_POLL_FAILURES)
def poll_moex_trades() -> None:
    """Дочитывание ленты сделок MOEX для бумаг с `track_trades=True`."""
    asyncio.run(poll_trades())
