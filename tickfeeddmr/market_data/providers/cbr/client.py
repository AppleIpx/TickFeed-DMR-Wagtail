import logging
import ssl
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import httpx
from defusedxml import ElementTree

from tickfeeddmr.market_data.providers.cbr.types import CbrRateRow
from tickfeeddmr.market_data.providers.exceptions import ProviderResponseError
from tickfeeddmr.market_data.providers.http_retry import RetryingHttpClient, RetryPolicy

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date
    from xml.etree.ElementTree import Element

logger = logging.getLogger(__name__)

DAILY_RATES_PATH = "/scripts/XML_daily.asp"

CONNECT_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0

MAX_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 4.0
BACKOFF_MULTIPLIER = 2
BACKOFF_JITTER = 0.2

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_NON_RETRYABLE_TRANSPORT_ERRORS = (
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
    httpx.ProxyError,
)
_NON_RETRYABLE_CAUSES = (ssl.SSLCertVerificationError,)

ERROR_REASON_MAX_CHARS = 200


class CbrDailyRatesClient:
    """Клиент к `XML_daily.asp` — все действующие курсы валют одним запросом.

    Все запросы идут через `_get`: повторы с backoff на сетевых сбоях и
    статусах 429/500/502/503/504, после исчерпания — `ProviderConnectionError`
    """

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._http = RetryingHttpClient(
            base_url=base_url,
            client=client,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            request_timeout=REQUEST_TIMEOUT_SECONDS,
            logger=logger,
        )

    @property
    def last_failure_reason(self) -> str | None:
        """Причина последней неудачной попытки текущего (или последнего) запроса."""
        return self._http.last_failure_reason

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_daily_rates(self) -> tuple[date, Sequence[CbrRateRow]]:
        """Официальная дата курса (`ValCurs[@Date]`) и курсы всех валют на неё.

        Строки, которые не удалось разобрать (нет обязательного поля,
        нечисловое значение), пропускаются с одной строкой WARNING на
        строку — единичный "битый" `Valute` не должен обрушивать весь
        прогон, как и в `consume_market_data_stream`.
        """
        response = await self._get(DAILY_RATES_PATH)
        return _parse_daily_rates(response.content)

    async def _get(self, path: str) -> httpx.Response:
        """GET с повторами; возвращает только успешный (не-ошибочный) ответ."""
        policy = RetryPolicy(
            max_attempts=MAX_ATTEMPTS,
            initial_backoff_seconds=INITIAL_BACKOFF_SECONDS,
            max_backoff_seconds=MAX_BACKOFF_SECONDS,
            backoff_multiplier=BACKOFF_MULTIPLIER,
            backoff_jitter=BACKOFF_JITTER,
            retryable_status_codes=RETRYABLE_STATUS_CODES,
            non_retryable_transport_errors=_NON_RETRYABLE_TRANSPORT_ERRORS,
            non_retryable_causes=_NON_RETRYABLE_CAUSES,
            error_reason_max_chars=ERROR_REASON_MAX_CHARS,
            log_label="ЦБ РФ",
            error_label="CBR",
        )
        return await self._http.get(path, policy=policy)


def _parse_daily_rates(content: bytes) -> tuple[date, Sequence[CbrRateRow]]:
    """Разобрать тело `XML_daily.asp` — дату курса и построчные ставки."""
    root = ElementTree.fromstring(content)
    date_attr = root.attrib.get("Date")
    if not date_attr:
        msg = "CBR XML_daily.asp response has no Date attribute on ValCurs"
        raise ProviderResponseError(msg)
    effective_date = datetime.strptime(date_attr, "%d.%m.%Y").replace(tzinfo=UTC).date()

    rows = []
    for valute in root.findall("Valute"):
        row = _row_from_element(valute)
        if row is not None:
            rows.append(row)
    return effective_date, rows


def _row_from_element(valute: Element) -> CbrRateRow | None:
    cbr_id = valute.attrib.get("ID")
    char_code = valute.findtext("CharCode")
    nominal_text = valute.findtext("Nominal")
    vunit_rate_text = valute.findtext("VunitRate")
    if not (cbr_id and char_code and nominal_text and vunit_rate_text):
        logger.warning(
            f"ЦБ РФ: пропущена строка Valute без обязательных полей: {cbr_id}",
        )
        return None
    try:
        nominal = int(nominal_text)
        rate = Decimal(vunit_rate_text.replace(",", "."))
    except (ValueError, InvalidOperation) as exc:
        logger.warning(
            f"ЦБ РФ: не удалось разобрать курс {cbr_id} ({char_code}): {exc}",
        )
        return None
    if nominal <= 0:
        logger.warning(f"ЦБ РФ: неположительный Nominal у {cbr_id} ({char_code})")
        return None
    return CbrRateRow(
        cbr_id=cbr_id,
        char_code=char_code,
        nominal=nominal,
        rate=rate,
    )
