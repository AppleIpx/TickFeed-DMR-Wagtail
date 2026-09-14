from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING

import httpx
import msgspec

from tickfeeddmr.market_data.providers.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class RetryPolicy(msgspec.Struct, frozen=True):
    """Параметры одного вызова `RetryingHttpClient.get` — своя копия на запрос."""

    max_attempts: int
    initial_backoff_seconds: float
    max_backoff_seconds: float
    backoff_multiplier: float
    backoff_jitter: float
    retryable_status_codes: frozenset[int]
    non_retryable_transport_errors: tuple[type[httpx.TransportError], ...]
    non_retryable_causes: tuple[type[BaseException], ...]
    error_reason_max_chars: int
    log_label: str
    error_label: str
    attempt_deadline_seconds: float | None = None


def iter_error_chain(exc: BaseException) -> Iterator[BaseException]:
    """`exc` и его причины по `__cause__`/`__context__`, с защитой от циклов."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_non_retryable(exc: httpx.TransportError, policy: RetryPolicy) -> bool:
    if isinstance(exc, policy.non_retryable_transport_errors):
        return True
    return any(
        isinstance(link, policy.non_retryable_causes) for link in iter_error_chain(exc)
    )


def describe_error(exc: httpx.TransportError, policy: RetryPolicy) -> str:
    """`ConnectError ([Errno 111] Connection refused)` — тип и усечённый текст.

    Текст приводится к одной строке (все пробельные символы, включая
    CR/LF, схлопываются в пробел) и режется до
    `policy.error_reason_max_chars` — он попадает в строки лога, и перевод
    строки внутри позволил бы подделать соседнюю запись. Вызывается только
    для повторяемых ошибок: `httpx.ProxyError`, чей текст может содержать
    URL прокси с учётными данными, неповторяемый и сюда не доходит.
    """
    name = type(exc).__name__
    text = " ".join(str(exc).split())[: policy.error_reason_max_chars]
    return f"{name} ({text})" if text else name


def backoff_delay(attempt: int, policy: RetryPolicy) -> float:
    """Пауза после неудачной попытки `attempt` (с 1): рост от initial до max ±jitter."""
    base = min(
        policy.max_backoff_seconds,
        policy.initial_backoff_seconds * policy.backoff_multiplier ** (attempt - 1),
    )
    # Jitter для рассинхронизации повторов, не криптография.
    return base * random.uniform(  # noqa: S311
        1 - policy.backoff_jitter,
        1 + policy.backoff_jitter,
    )


def raise_for_status(
    response: httpx.Response,
    *,
    logger: logging.Logger,
    policy: RetryPolicy,
) -> None:
    if response.is_error:
        logger.error(
            f"Ошибка {policy.log_label} {response.status_code}: {response.text[:500]}",
        )
        msg = f"{policy.error_label} request failed with status {response.status_code}"
        raise ProviderResponseError(msg)


class RetryingHttpClient:
    """`httpx.AsyncClient` + повторы GET с backoff — общая часть клиентов ISS/ЦБ РФ.

    Все запросы идут через `get`: повторы с backoff на сетевых сбоях и
    статусах из `policy.retryable_status_codes`, после исчерпания —
    `ProviderConnectionError`. GET — идемпотентный, повтор безопасен.
    """

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None,
        connect_timeout: float,
        request_timeout: float,
        logger: logging.Logger,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(request_timeout, connect=connect_timeout),
        )
        self._logger = logger
        self._last_failure_reason: str | None = None

    @property
    def last_failure_reason(self) -> str | None:
        """Причина последней неудачной попытки текущего (или последнего) запроса.

        Сбрасывается в начале каждого запроса. Нужна вызывающему коду,
        когда запрос оборван извне — отменой по бюджету прогона, — и
        `ProviderConnectionError` с причиной внутри так и не поднялся:
        иначе в логе не видно, на чём висели попытки. `None` — ни одна
        попытка текущего запроса ещё не провалилась (например, бюджет
        оборвал первую же).
        """
        return self._last_failure_reason

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        path: str,
        *,
        policy: RetryPolicy,
        params: Mapping[str, str | int] | None = None,
    ) -> httpx.Response:
        """GET с повторами; возвращает только успешный (не-ошибочный) ответ."""
        started = time.monotonic()
        self._last_failure_reason = None
        last_error: Exception | None = None
        reason = ""
        for attempt in range(1, policy.max_attempts + 1):
            try:
                response = await self._request(path, params, policy)
            except httpx.TransportError as exc:
                if is_non_retryable(exc, policy):
                    raise
                last_error, reason = exc, describe_error(exc, policy)
            except TimeoutError as exc:
                # Только собственный дедлайн попытки: чужая отмена приходит
                # как `CancelledError` и сюда не попадает.
                last_error = exc
                reason = (
                    f"attempt deadline {policy.attempt_deadline_seconds:g}s exceeded"
                )
            else:
                if response.status_code not in policy.retryable_status_codes:
                    raise_for_status(response, logger=self._logger, policy=policy)
                    if attempt > 1:
                        self._logger.info(
                            f"{policy.log_label} {path}: ответ получен с "
                            f"{attempt}-й попытки за {time.monotonic() - started:.1f} "
                            f"с (последняя ошибка: {reason})",
                        )
                    return response
                # Тело ответа 5xx/429 не логируем на каждой попытке —
                # только код статуса попадёт в итоговую ошибку.
                last_error = ProviderResponseError(
                    f"{policy.error_label} request failed with status "
                    f"{response.status_code}",
                )
                reason = f"HTTP {response.status_code}"
            self._last_failure_reason = reason

            if attempt < policy.max_attempts:
                delay = backoff_delay(attempt, policy)
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(
                        f"{policy.log_label} {path}: попытка "
                        f"{attempt}/{policy.max_attempts} не удалась ({reason}), "
                        f"повтор через {delay:.1f} с",
                    )
                await asyncio.sleep(delay)

        elapsed = time.monotonic() - started
        msg = (
            f"{policy.error_label} unreachable: {reason} "
            f"after {policy.max_attempts} attempts in {elapsed:.1f}s (GET {path})"
        )
        raise ProviderConnectionError(
            msg,
            reason=reason,
            attempts=policy.max_attempts,
            elapsed_seconds=elapsed,
        ) from last_error

    async def _request(
        self,
        path: str,
        params: Mapping[str, str | int] | None,
        policy: RetryPolicy,
    ) -> httpx.Response:
        if policy.attempt_deadline_seconds is None:
            return await self._client.get(path, params=params)
        async with asyncio.timeout(policy.attempt_deadline_seconds):
            return await self._client.get(path, params=params)
