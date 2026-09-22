from __future__ import annotations

import ssl
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import pytest

from tickfeeddmr.market_data.providers.cbr.client import (
    MAX_ATTEMPTS,
    CbrDailyRatesClient,
    _parse_daily_rates,
)
from tickfeeddmr.market_data.providers.cbr.types import CbrRateRow
from tickfeeddmr.market_data.providers.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

BASE_URL = "https://cbr.testnet.example"

pytestmark = pytest.mark.usefixtures("fast_cbr_backoff")


def _daily_rates_xml(body: str) -> bytes:
    header = '<?xml version="1.0" encoding="windows-1251"?>'
    return f"{header}\n{body}".encode("cp1251")


VALID_XML = _daily_rates_xml(
    """
    <ValCurs Date="12.09.2026" name="Foreign Currency Market">
        <Valute ID="R01235">
            <NumCode>840</NumCode>
            <CharCode>USD</CharCode>
            <Nominal>1</Nominal>
            <Name>Доллар США</Name>
            <Value>92,4574</Value>
            <VunitRate>92,4574</VunitRate>
        </Valute>
        <Valute ID="R01820">
            <NumCode>392</NumCode>
            <CharCode>JPY</CharCode>
            <Nominal>100</Nominal>
            <Name>Иена</Name>
            <Value>63,1234</Value>
            <VunitRate>0,631234</VunitRate>
        </Valute>
    </ValCurs>
    """,
)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> CbrDailyRatesClient:
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url=BASE_URL, transport=transport)
    return CbrDailyRatesClient(base_url=BASE_URL, client=async_client)


def test_parse_daily_rates_realistic_xml_with_nominal() -> None:
    effective_date, rows = _parse_daily_rates(VALID_XML)

    assert effective_date == date(2026, 9, 12)
    assert rows == [
        CbrRateRow(
            cbr_id="R01235",
            char_code="USD",
            nominal=1,
            rate=Decimal("92.4574"),
        ),
        CbrRateRow(
            cbr_id="R01820",
            char_code="JPY",
            nominal=100,
            rate=Decimal("0.631234"),
        ),
    ]
    # VunitRate уже курс за одну единицу валюты — Nominal здесь только
    # проверяется на положительность, в расчёт курса не участвует.
    assert rows[1].rate == Decimal("0.631234")


def test_parse_daily_rates_skips_malformed_rows(
    caplog: pytest.LogCaptureFixture,
) -> None:
    xml = _daily_rates_xml(
        """
        <ValCurs Date="12.09.2026" name="Foreign Currency Market">
            <Valute ID="R01235">
                <NumCode>840</NumCode>
                <CharCode>USD</CharCode>
                <Nominal>1</Nominal>
                <Name>Доллар США</Name>
                <VunitRate>92,4574</VunitRate>
            </Valute>
            <Valute ID="R01239">
                <NumCode>978</NumCode>
                <Nominal>1</Nominal>
                <Name>Евро</Name>
                <VunitRate>100,1234</VunitRate>
            </Valute>
            <Valute ID="R01700J">
                <NumCode>417</NumCode>
                <CharCode>KGS</CharCode>
                <Nominal>10</Nominal>
                <Name>Сомони</Name>
                <VunitRate>not-a-number</VunitRate>
            </Valute>
            <Valute ID="R01820">
                <NumCode>392</NumCode>
                <CharCode>JPY</CharCode>
                <Nominal>0</Nominal>
                <Name>Иена</Name>
                <VunitRate>0,631234</VunitRate>
            </Valute>
        </ValCurs>
        """,
    )

    with caplog.at_level("WARNING"):
        effective_date, rows = _parse_daily_rates(xml)

    assert effective_date == date(2026, 9, 12)
    # Только валидная строка USD дожила до результата — три "битых" строки
    # (нет CharCode, нечисловой VunitRate, неположительный Nominal) пропущены.
    assert rows == [
        CbrRateRow(
            cbr_id="R01235",
            char_code="USD",
            nominal=1,
            rate=Decimal("92.4574"),
        ),
    ]
    assert len(caplog.records) == 3  # noqa: PLR2004
    assert all(record.levelname == "WARNING" for record in caplog.records)


def test_parse_daily_rates_skips_row_without_vunit_rate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Value без VunitRate — VunitRate теперь обязателен, Value больше не
    # читается вообще, так что такая строка не может быть разобрана.
    xml = _daily_rates_xml(
        """
        <ValCurs Date="12.09.2026" name="Foreign Currency Market">
            <Valute ID="R01235">
                <NumCode>840</NumCode>
                <CharCode>USD</CharCode>
                <Nominal>1</Nominal>
                <Name>Доллар США</Name>
                <Value>92,4574</Value>
            </Valute>
        </ValCurs>
        """,
    )

    with caplog.at_level("WARNING"):
        effective_date, rows = _parse_daily_rates(xml)

    assert effective_date == date(2026, 9, 12)
    assert rows == []
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert "без обязательных полей" in caplog.records[0].message


def test_parse_daily_rates_missing_date_attribute_raises() -> None:
    xml = _daily_rates_xml(
        '<ValCurs name="Foreign Currency Market"></ValCurs>',
    )

    with pytest.raises(ProviderResponseError):
        _parse_daily_rates(xml)


async def test_get_daily_rates_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/scripts/XML_daily.asp"
        return httpx.Response(200, content=VALID_XML)

    client = _client(handler)
    effective_date, rows = await client.get_daily_rates()
    await client.aclose()

    assert effective_date == date(2026, 9, 12)
    assert len(rows) == 2  # noqa: PLR2004


async def test_get_daily_rates_retries_and_recovers() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            msg = "connection refused"
            raise httpx.ConnectError(msg, request=request)
        if call_count == 2:  # noqa: PLR2004
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, content=VALID_XML)

    client = _client(handler)
    effective_date, rows = await client.get_daily_rates()
    await client.aclose()

    assert call_count == 3  # noqa: PLR2004
    assert effective_date == date(2026, 9, 12)
    assert len(rows) == 2  # noqa: PLR2004


async def test_get_daily_rates_raises_connection_error_retries_exhausted() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, text="boom")

    client = _client(handler)
    try:
        with pytest.raises(ProviderConnectionError) as exc_info:
            await client.get_daily_rates()
        assert client.last_failure_reason is not None
    finally:
        await client.aclose()

    assert call_count == MAX_ATTEMPTS
    assert exc_info.value.attempts == MAX_ATTEMPTS
    assert exc_info.value.reason is not None
    assert exc_info.value.elapsed_seconds is not None


async def test_get_daily_rates_proxy_error_is_not_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        msg = "proxy refused connection"
        raise httpx.ProxyError(msg, request=request)

    client = _client(handler)
    try:
        with pytest.raises(httpx.ProxyError):
            await client.get_daily_rates()
    finally:
        await client.aclose()

    assert call_count == 1


async def test_get_daily_rates_unsupported_protocol_is_not_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        msg = "unsupported protocol"
        raise httpx.UnsupportedProtocol(msg, request=request)

    client = _client(handler)
    try:
        with pytest.raises(httpx.UnsupportedProtocol):
            await client.get_daily_rates()
    finally:
        await client.aclose()

    assert call_count == 1


async def test_get_daily_rates_tls_verification_failure_is_not_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")
        msg = "ssl failure"
        raise httpx.ConnectError(msg, request=request) from cert_error

    client = _client(handler)
    try:
        with pytest.raises(httpx.ConnectError):
            await client.get_daily_rates()
    finally:
        await client.aclose()

    assert call_count == 1


DYNAMIC_RATES_XML = _daily_rates_xml(
    """
    <ValCurs ID="R01235" DateRange1="01.09.2026" DateRange2="12.09.2026" name="USD">
        <Record Date="10.09.2026" Id="R01235">
            <Nominal>1</Nominal>
            <Value>91,1234</Value>
            <VunitRate>91,1234</VunitRate>
        </Record>
        <Record Date="11.09.2026" Id="R01235">
            <Nominal>1</Nominal>
            <Value>91,5678</Value>
            <VunitRate>91,5678</VunitRate>
        </Record>
    </ValCurs>
    """,
)


async def test_get_dynamic_rates_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/scripts/XML_dynamic.asp"
        assert request.url.params["VAL_NM_RQ"] == "R01235"
        assert request.url.params["date_req1"] == "01/09/2026"
        assert request.url.params["date_req2"] == "12/09/2026"
        return httpx.Response(200, content=DYNAMIC_RATES_XML)

    client = _client(handler)
    rows = await client.get_dynamic_rates(
        "R01235",
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 12),
    )
    await client.aclose()

    assert [(row.effective_date, row.rate) for row in rows] == [
        (date(2026, 9, 10), Decimal("91.1234")),
        (date(2026, 9, 11), Decimal("91.5678")),
    ]


async def test_get_dynamic_rates_raises_connection_error_retries_exhausted() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, text="boom")

    client = _client(handler)
    try:
        with pytest.raises(ProviderConnectionError) as exc_info:
            await client.get_dynamic_rates(
                "R01235",
                date_from=date(2026, 9, 1),
                date_to=date(2026, 9, 12),
            )
    finally:
        await client.aclose()

    assert call_count == MAX_ATTEMPTS
    assert exc_info.value.attempts == MAX_ATTEMPTS


async def test_get_daily_rates_non_retryable_status_is_not_retried() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(404, text="not found")

    client = _client(handler)
    try:
        with pytest.raises(ProviderResponseError):
            await client.get_daily_rates()
    finally:
        await client.aclose()

    assert call_count == 1
