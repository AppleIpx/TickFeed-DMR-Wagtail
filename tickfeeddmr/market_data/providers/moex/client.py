import logging
import ssl
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import quote

import httpx

from tickfeeddmr.market_data.providers.http_retry import RetryingHttpClient, RetryPolicy
from tickfeeddmr.market_data.providers.moex.timeutils import (
    MOSCOW_TZ,
    board_updatetime_to_utc,
    moscow_timestamp_to_utc,
)
from tickfeeddmr.market_data.providers.moex.types import (
    MoexBoardRow,
    MoexCandleRow,
    MoexTradeRow,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import date

logger = logging.getLogger(__name__)

BOARD_SECURITIES_PATH_TEMPLATE = (
    "/iss/engines/stock/markets/shares/boards/{board}/securities.json"
)
TRADES_PATH_TEMPLATE = (
    "/iss/engines/stock/markets/shares/securities/{secid}/trades.json"
)
CANDLES_PATH_TEMPLATE = (
    "/iss/engines/stock/markets/shares/securities/{secid}/candles.json"
)
CONNECT_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0
ATTEMPT_DEADLINE_SECONDS = 12.0

MAX_ATTEMPTS = 7
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0
BACKOFF_MULTIPLIER = 2
BACKOFF_JITTER = 0.2

# 500–504 — "временные проблемы" по руководству ISS v1.4 (повторить тот же
# адрес через небольшой промежуток); 429 — на случай лимитов, которых в
# документации нет. 501/505 и прочие 5xx — постоянные, повтор бесполезен.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_NON_RETRYABLE_TRANSPORT_ERRORS = (
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
    httpx.ProxyError,
)
_NON_RETRYABLE_CAUSES = (ssl.SSLCertVerificationError,)

# Потолок длины текста причины в сообщении `ProviderConnectionError` (и,
# значит, в строках лога тика) — хватает на "[Errno 111] Connection
# refused"/"Name or service not known"/текст SSL-ошибки.
ERROR_REASON_MAX_CHARS = 200

# Задокументированный размер страницы ленты сделок ISS — используется
# вызывающим кодом (`poll_trades`), чтобы отличить последнюю страницу
# от неполной: если пришло меньше строк, чем это, дальше читать нечего.
TRADES_PAGE_ROWS = 5000


class MoexIssClient:
    """Клиент к ISS MOEX: снимок борда, лента сделок, свечи.

    Все ответы ISS — формат `{"<блок>": {"columns": [...], "data": [...]}}`;
    индексы колонок ищутся по имени через словарь `{имя: индекс}`, а не
    хардкодятся позиционно — состав колонок ISS меняет.

    Все запросы идут через `_get`: повторы с backoff на сетевых сбоях и
    статусах 429/500/502/503/504, после исчерпания —
    `ProviderConnectionError`. Все запросы ISS — идемпотентные GET, повтор
    безопасен.
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
        """Причина последней неудачной попытки текущего (или последнего) запроса.

        Сбрасывается в начале каждого запроса. Нужна вызывающему коду,
        когда запрос оборван извне — отменой по бюджету прогона, — и
        `ProviderConnectionError` с причиной внутри так и не поднялся:
        иначе в логе не видно, на чём висели попытки. `None` — ни одна
        попытка текущего запроса ещё не провалилась (например, бюджет
        оборвал первую же).
        """
        return self._http.last_failure_reason

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_board_snapshot(self, board: str) -> Sequence[MoexBoardRow]:
        """Снимок борда одним запросом — цены и объёмы по всем бумагам борда."""
        response = await self._get(
            BOARD_SECURITIES_PATH_TEMPLATE.format(board=board),
            params={"iss.meta": "off", "iss.only": "marketdata"},
        )
        block = response.json()["marketdata"]
        columns = block["columns"]
        trading_day = datetime.now(MOSCOW_TZ).date()
        return [
            self._board_row_from_columns(columns, row, trading_day)
            for row in block["data"]
        ]

    async def get_trades_page(
        self,
        secid: str,
        *,
        since_trade_no: int | None = None,
    ) -> Sequence[MoexTradeRow]:
        """Одна страница ленты сделок (до `TRADES_PAGE_ROWS` строк).

        Без `since_trade_no` — самые старые доступные сделки за сессию;
        с ним — продолжение от `TRADENO=since_trade_no` через
        `next_trade=1`. Дочитывание нескольких страниц за один прогон
        задачи — забота вызывающего кода (`poll_moex_trades`), не клиента.
        """
        params: dict[str, str | int] = {"iss.meta": "off"}
        if since_trade_no is not None:
            params["tradeno"] = since_trade_no
            params["next_trade"] = 1
        response = await self._get(
            TRADES_PATH_TEMPLATE.format(secid=quote(secid, safe="")),
            params=params,
        )
        block = response.json()["trades"]
        columns = block["columns"]
        return [self._trade_row_from_columns(columns, row) for row in block["data"]]

    async def get_candles(
        self,
        secid: str,
        *,
        start: datetime,
        end: datetime | None,
        interval: str,
    ) -> Sequence[MoexCandleRow]:
        """Одна страница свечей за `[start, end)`.

        Постраничность нескольких вызовов — на вызывающем коде.
        """
        params: dict[str, str] = {
            "iss.meta": "off",
            "interval": interval,
            "from": start.date().isoformat(),
        }
        if end is not None:
            params["till"] = end.date().isoformat()
        response = await self._get(
            CANDLES_PATH_TEMPLATE.format(secid=quote(secid, safe="")),
            params=params,
        )
        block = response.json()["candles"]
        columns = block["columns"]
        return [self._candle_row_from_columns(columns, row) for row in block["data"]]

    async def _get(
        self,
        path: str,
        *,
        params: Mapping[str, str | int],
    ) -> httpx.Response:
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
            log_label="MOEX ISS",
            error_label="MOEX ISS",
            attempt_deadline_seconds=ATTEMPT_DEADLINE_SECONDS,
        )
        return await self._http.get(path, params=params, policy=policy)

    @staticmethod
    def _board_row_from_columns(
        columns: Sequence[str],
        row: Sequence[object],
        trading_day: date,
    ) -> MoexBoardRow:
        get = _column_getter(columns, row)
        updatetime = get("UPDATETIME")
        timestamp = (
            board_updatetime_to_utc(trading_day, cast("str", updatetime))
            if updatetime
            else datetime.now(UTC)
        )
        return MoexBoardRow(
            secid=cast("str", get("SECID")),
            last=_to_decimal(get("LAST")),
            open=_to_decimal(get("OPEN")),
            high=_to_decimal(get("HIGH")),
            low=_to_decimal(get("LOW")),
            change=_to_decimal(get("LASTCHANGE")),
            change_percent=_to_decimal(get("LASTCHANGEPRCNT")),
            volume=_to_int(get("VOLTODAY")),
            value=_to_decimal(get("VALTODAY")),
            num_trades=_to_int(get("NUMTRADES")),
            timestamp=timestamp,
            trading_status=cast("str", get("TRADINGSTATUS") or ""),
        )

    @staticmethod
    def _trade_row_from_columns(
        columns: Sequence[str],
        row: Sequence[object],
    ) -> MoexTradeRow:
        get = _column_getter(columns, row)
        buysell = get("BUYSELL")
        side: Literal["buy", "sell"] = "buy" if buysell == "B" else "sell"
        return MoexTradeRow(
            trade_id=int(cast("int", get("TRADENO"))),
            price=Decimal(str(get("PRICE"))),
            quantity=int(cast("int", get("QUANTITY"))),
            side=side,
            timestamp=moscow_timestamp_to_utc(cast("str", get("SYSTIME"))),
            period=str(get("PERIOD") or ""),
        )

    @staticmethod
    def _candle_row_from_columns(
        columns: Sequence[str],
        row: Sequence[object],
    ) -> MoexCandleRow:
        get = _column_getter(columns, row)
        return MoexCandleRow(
            open=_to_decimal(get("open")) or Decimal(0),
            high=_to_decimal(get("high")) or Decimal(0),
            low=_to_decimal(get("low")) or Decimal(0),
            close=_to_decimal(get("close")) or Decimal(0),
            value=_to_decimal(get("value")) or Decimal(0),
            volume=_to_int(get("volume")) or 0,
            begin=moscow_timestamp_to_utc(cast("str", get("begin"))),
            end=moscow_timestamp_to_utc(cast("str", get("end"))),
        )


def _column_getter(
    columns: Sequence[str],
    row: Sequence[object],
) -> Callable[[str], object]:
    index = {name: position for position, name in enumerate(columns)}

    def get(name: str) -> object:
        position = index.get(name)
        return None if position is None else row[position]

    return get


def _to_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _to_int(value: object) -> int | None:
    return None if value is None else int(cast("int", value))
