from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
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

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_django.fixtures import Settings as PytestDjangoSettings

    from tickfeeddmr.market_data.models import FiatCurrency

pytestmark = pytest.mark.django_db(transaction=True)

CLIENT_TARGET = "tickfeeddmr.market_data.services.cbr_polling.rates.CbrDailyRatesClient"
LOCK_TTL_SECONDS = 30

# 12.09.2026 00:00 МСК (UTC+3, без переходов на летнее время) —
# 11.09.2026 21:00 UTC.
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
        await poll_rates()

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
            await poll_rates()

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
        await poll_rates()

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
        await poll_rates()

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

    for _ in range(2):
        fake_client = _FakeCbrClient(rows=[row])
        with patch(CLIENT_TARGET, return_value=fake_client):
            await poll_rates()

    assert await FiatPriceSnapshot.objects.acount() == 1


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
        await poll_rates()

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
        await poll_rates()

    assert exc_info.value.last_failure_reason == "ConnectError (timeout)"
    assert fake_client.aclose_called is True
    assert any("не ответил за бюджет" in r.message for r in caplog.records)
