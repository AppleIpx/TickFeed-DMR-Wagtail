from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.conf import settings

from tickfeeddmr.market_data.models import FiatPriceSnapshot
from tickfeeddmr.market_data.providers.cbr.types import CbrRateRow
from tickfeeddmr.market_data.providers.exceptions import ProviderConnectionError
from tickfeeddmr.market_data.services.cbr_polling import poll_rates
from tickfeeddmr.market_data.services.cbr_polling.errors import (
    CbrPollBudgetExceededError,
)
from tickfeeddmr.market_data.services.cbr_polling.rates import CBR_LOCK_KEY
from tickfeeddmr.market_data.services.locks import redis_lock
from tickfeeddmr.market_data.tests.factories import (
    FiatCurrencyFactory,
    FiatPriceSnapshotFactory,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_django.fixtures import Settings as PytestDjangoSettings

    from tickfeeddmr.market_data.models import FiatCurrency

pytestmark = pytest.mark.django_db(transaction=True)

CLIENT_TARGET = "tickfeeddmr.market_data.services.cbr_polling.rates.CbrDailyRatesClient"
LOCK_TTL_SECONDS = 30

TODAY = date(2026, 9, 11)

# 12.09.2026 00:00 МСК (UTC+3, без переходов на летнее время) —
# 11.09.2026 21:00 UTC. Это TODAY + 1 день — тот самый `target`, который
# `run()` вычисляет из `today`.
EFFECTIVE_DATE = date(2026, 9, 12)
EXPECTED_TIMESTAMP = datetime(2026, 9, 11, 21, 0, 0, tzinfo=UTC)


class _FakeCbrClient:
    """Замена `CbrDailyRatesClient` без сети — управляемый результат/сбой/задержка."""

    def __init__(
        self,
        *,
        rows: Sequence[CbrRateRow] = (),
        effective_date: date = EFFECTIVE_DATE,
        last_failure_reason: str | None = None,
        error: Exception | None = None,
        sleep_seconds: float | None = None,
    ) -> None:
        self._rows = rows
        self._effective_date = effective_date
        self.last_failure_reason = last_failure_reason
        self._error = error
        self._sleep_seconds = sleep_seconds
        self.aclose_called = False

    async def get_daily_rates(self) -> tuple[date, Sequence[CbrRateRow]]:
        if self._sleep_seconds is not None:
            await asyncio.sleep(self._sleep_seconds)
        if self._error is not None:
            raise self._error
        return self._effective_date, self._rows

    async def aclose(self) -> None:
        self.aclose_called = True


async def test_poll_rates_skips_when_no_active_currencies(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch(CLIENT_TARGET) as client_cls, caplog.at_level(logging.INFO):
        await poll_rates(today=TODAY)

    client_cls.assert_not_called()
    assert any("собирать нечего" in r.message for r in caplog.records)


async def test_poll_rates_skips_when_lock_is_busy(
    caplog: pytest.LogCaptureFixture,
    fiat_currency: FiatCurrency,
) -> None:
    async with redis_lock(
        redis_url=settings.REDIS_URL,
        key=CBR_LOCK_KEY,
        ttl_seconds=LOCK_TTL_SECONDS,
    ):
        with patch(CLIENT_TARGET) as client_cls, caplog.at_level(logging.INFO):
            await poll_rates(today=TODAY)

    client_cls.assert_not_called()
    assert any("лок занят" in r.message for r in caplog.records)


async def test_poll_rates_happy_path_writes_snapshot(
    fiat_currency: FiatCurrency,
) -> None:
    fiat_currency.cbr_id = "R01235"
    await fiat_currency.asave(update_fields=["cbr_id"])
    row = CbrRateRow(
        cbr_id="R01235",
        char_code="USD",
        nominal=1,
        rate=Decimal("92.4574"),
    )
    fake_client = _FakeCbrClient(rows=[row])

    with patch(CLIENT_TARGET, return_value=fake_client):
        await poll_rates(today=TODAY)

    snapshot = await FiatPriceSnapshot.objects.aget(asset=fiat_currency)
    assert snapshot.price == Decimal("92.4574")
    assert snapshot.effective_date == EFFECTIVE_DATE
    assert snapshot.timestamp == EXPECTED_TIMESTAMP


async def test_poll_rates_skips_unknown_cbr_id(
    fiat_currency: FiatCurrency,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fiat_currency.cbr_id = "R01235"
    await fiat_currency.asave(update_fields=["cbr_id"])
    known_row = CbrRateRow(
        cbr_id="R01235",
        char_code="USD",
        nominal=1,
        rate=Decimal("92.4574"),
    )
    unknown_row = CbrRateRow(
        cbr_id="R99999",
        char_code="XXX",
        nominal=1,
        rate=Decimal("1"),
    )
    fake_client = _FakeCbrClient(rows=[known_row, unknown_row])

    with patch(CLIENT_TARGET, return_value=fake_client), caplog.at_level(logging.INFO):
        await poll_rates(today=TODAY)

    assert await FiatPriceSnapshot.objects.acount() == 1
    assert any("пропущено (нет активной валюты) 1" in r.message for r in caplog.records)


async def test_poll_rates_is_idempotent_for_same_effective_date(
    fiat_currency: FiatCurrency,
) -> None:
    fiat_currency.cbr_id = "R01235"
    await fiat_currency.asave(update_fields=["cbr_id"])
    row = CbrRateRow(
        cbr_id="R01235",
        char_code="USD",
        nominal=1,
        rate=Decimal("92.4574"),
    )
    fake_client = _FakeCbrClient(rows=[row])

    with patch(CLIENT_TARGET, return_value=fake_client) as client_cls:
        await poll_rates(today=TODAY)
        await poll_rates(today=TODAY)

    # Второй прогон выходит на preflight-проверке (курс на `target` уже
    # есть у единственной активной валюты) — клиент создаётся только
    # на первом прогоне, до сети дело не доходит вовсе.
    assert await FiatPriceSnapshot.objects.acount() == 1
    assert client_cls.call_count == 1


async def test_poll_rates_provider_connection_error_propagates(
    fiat_currency: FiatCurrency,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = ProviderConnectionError(
        "CBR unreachable: boom after 3 attempts in 1.2s (GET /scripts/XML_daily.asp)",
        reason="boom",
        attempts=3,
        elapsed_seconds=1.2,
    )
    fake_client = _FakeCbrClient(error=error)

    with (
        patch(CLIENT_TARGET, return_value=fake_client),
        caplog.at_level(logging.WARNING),
        pytest.raises(ProviderConnectionError),
    ):
        await poll_rates(today=TODAY)

    assert fake_client.aclose_called is True
    assert any("ЦБ РФ недоступен" in r.message for r in caplog.records)


async def test_poll_rates_budget_exceeded_raises_with_last_failure_reason(
    fiat_currency: FiatCurrency,
    caplog: pytest.LogCaptureFixture,
    settings: PytestDjangoSettings,
) -> None:
    settings.CBR_POLL_BUDGET_SECONDS = 0.05
    fake_client = _FakeCbrClient(
        sleep_seconds=1.0,
        last_failure_reason="ConnectError (timeout)",
    )

    with (
        patch(CLIENT_TARGET, return_value=fake_client),
        caplog.at_level(logging.WARNING),
        pytest.raises(CbrPollBudgetExceededError) as exc_info,
    ):
        await poll_rates(today=TODAY)

    assert exc_info.value.last_failure_reason == "ConnectError (timeout)"
    assert fake_client.aclose_called is True
    assert any("не ответил за бюджет" in r.message for r in caplog.records)


async def test_poll_rates_goes_to_network_when_only_today_has_snapshot(
    fiat_currency: FiatCurrency,
) -> None:
    # Снимок уже есть, но на TODAY, а не на target (TODAY + 1) — preflight
    # обязан увидеть "нет курса на target" и пойти в сеть, а не молча
    # решить, что валюта уже покрыта.
    fiat_currency.cbr_id = "R01235"
    await fiat_currency.asave(update_fields=["cbr_id"])
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=TODAY,
    )
    row = CbrRateRow(
        cbr_id="R01235",
        char_code="USD",
        nominal=1,
        rate=Decimal("92.4574"),
    )
    fake_client = _FakeCbrClient(rows=[row])

    with patch(CLIENT_TARGET, return_value=fake_client) as client_cls:
        await poll_rates(today=TODAY)

    client_cls.assert_called_once()
    assert await FiatPriceSnapshot.objects.filter(asset=fiat_currency).acount() == 2  # noqa: PLR2004
    assert await FiatPriceSnapshot.objects.filter(
        asset=fiat_currency,
        effective_date=EFFECTIVE_DATE,
    ).aexists()


async def test_poll_rates_preflight_skips_when_target_already_covered(
    fiat_currency: FiatCurrency,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=fiat_currency,
        effective_date=EFFECTIVE_DATE,
    )

    with patch(CLIENT_TARGET) as client_cls, caplog.at_level(logging.INFO):
        await poll_rates(today=TODAY)

    client_cls.assert_not_called()
    assert any("уже есть у всех 1 активных валют" in r.message for r in caplog.records)


async def test_poll_rates_not_yet_published_does_not_write(
    fiat_currency: FiatCurrency,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # ЦБ ещё отдаёт курс на TODAY, а не на target — это ожидаемое ожидание
    # следующего слота, не ошибка: исключений нет, запись не происходит.
    fiat_currency.cbr_id = "R01235"
    await fiat_currency.asave(update_fields=["cbr_id"])
    row = CbrRateRow(
        cbr_id="R01235",
        char_code="USD",
        nominal=1,
        rate=Decimal("92.4574"),
    )
    fake_client = _FakeCbrClient(rows=[row], effective_date=TODAY)

    with patch(CLIENT_TARGET, return_value=fake_client), caplog.at_level(logging.INFO):
        await poll_rates(today=TODAY)

    assert await FiatPriceSnapshot.objects.acount() == 0
    assert any("ждём следующий слот" in r.message for r in caplog.records)


async def test_poll_rates_already_up_to_date_with_partial_coverage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    covered = await sync_to_async(FiatCurrencyFactory.create)(cbr_id="R00001")
    uncovered = await sync_to_async(FiatCurrencyFactory.create)(cbr_id="R00002")
    await sync_to_async(FiatPriceSnapshotFactory.create)(
        asset=covered,
        effective_date=EFFECTIVE_DATE,
    )
    rows = [
        CbrRateRow(
            cbr_id=covered.cbr_id,
            char_code="USD",
            nominal=1,
            rate=Decimal("1"),
        ),
        CbrRateRow(
            cbr_id=uncovered.cbr_id,
            char_code="EUR",
            nominal=1,
            rate=Decimal("2"),
        ),
    ]
    fake_client = _FakeCbrClient(rows=rows)

    with patch(CLIENT_TARGET, return_value=fake_client), caplog.at_level(logging.INFO):
        await poll_rates(today=TODAY)

    snapshot_count = await FiatPriceSnapshot.objects.filter(
        effective_date=EFFECTIVE_DATE,
    ).acount()
    assert snapshot_count == 2  # noqa: PLR2004
    assert any("записано 1, уже было 1" in r.message for r in caplog.records)
