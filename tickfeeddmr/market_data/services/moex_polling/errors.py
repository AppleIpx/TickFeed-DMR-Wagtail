"""Ожидаемые исходы неудачного прогона опроса MOEX: бюджет и описание для лога.

Два ожидаемых (не баг) исхода, которые пуллеры не глотают: пишут одну
строку WARNING без трейса и пробрасывают исключение дальше, а задачи в
`market_data/tasks.py` объявляют оба в `throws` — Celery помечает тик
FAILURE, но логирует его как "raised expected" (INFO, без трейса), а не
как неожиданную ошибку:

- `ProviderConnectionError` — ISS недоступен после повторов
  `MoexIssClient`;
- `PollBudgetExceededError` — прогон не уложился в свой бюджет времени.
  Это не обязательно недоступность ISS (в ленте сделок общий дедлайн
  съедают и записи в БД между страницами, и законный догон), поэтому
  отдельный класс, а не `ProviderConnectionError`.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
    from tickfeeddmr.market_data.providers.moex import MoexProvider


class PollBudgetExceededError(Exception):
    """Прогон опроса MOEX не уложился в `MOEX_*_POLL_BUDGET_SECONDS`.

    Поднимается `poll_budget_scope` из `TimeoutError` дедлайна, с
    цепочкой от него. `last_failure_reason` — причина последней неудачной
    попытки запроса, оборванного бюджетом (`None`, если оборвана первая же
    попытка). Всё нужное для лога — и в самом сообщении: Celery логирует
    ожидаемые ошибки как `repr` исключения. В `args` — только сообщение,
    чтобы исключение восстанавливалось при unpickle между процессами
    prefork-пула.
    """

    def __init__(self, message: str, *, last_failure_reason: str | None = None) -> None:
        super().__init__(message)
        self.last_failure_reason = last_failure_reason


@asynccontextmanager
async def poll_budget_scope(
    *,
    deadline: float,
    budget_seconds: int,
    label: str,
    provider: MoexProvider,
) -> AsyncIterator[None]:
    """Абсолютный дедлайн прогона вокруг сетевого вызова → `PollBudgetExceededError`.

    Оборачивать только сетевой вызов провайдера, не запись в БД (async
    ORM выполняет запрос в потоке, отмена `await` поток не прерывает) и не
    `provider.aclose()`/снятие лока — те должны выполняться вне
    отменённого scope. `TimeoutError` дедлайна переводится в
    `PollBudgetExceededError` прямо здесь, вплотную к сетевому вызову, —
    чтобы вызывающий код не принял за исчерпание бюджета посторонний
    `TimeoutError`. Сырой `TimeoutError` из самого провайдера прийти не
    может: `MoexIssClient` его наружу не выпускает.
    """
    try:
        async with asyncio.timeout_at(deadline):
            yield
    except TimeoutError as exc:
        reason = provider.last_failure_reason
        msg = f"MOEX ISS: {label} не уложился в бюджет прогона ({budget_seconds} с)"
        if reason is not None:
            msg = f"{msg}; последняя неудачная попытка: {reason}"
        raise PollBudgetExceededError(msg, last_failure_reason=reason) from exc


def describe_connection_failure(exc: ProviderConnectionError) -> str:
    """`ConnectError ([Errno 111] Connection refused), попыток: 7 за 31 с`.

    Причину, число попыток и время заполняет `MoexIssClient`. Поля
    необязательны только на уровне типа общего `ProviderConnectionError`;
    на случай их отсутствия — сообщение исключения как есть.
    """
    if exc.reason is None or exc.attempts is None or exc.elapsed_seconds is None:
        return str(exc)
    return f"{exc.reason}, попыток: {exc.attempts} за {exc.elapsed_seconds:.0f} с"


def last_failure_note(exc: PollBudgetExceededError) -> str:
    """` (последняя неудачная попытка: …)` для WARNING по бюджету, если причина есть."""
    if exc.last_failure_reason is None:
        return ""
    return f" (последняя неудачная попытка: {exc.last_failure_reason})"
