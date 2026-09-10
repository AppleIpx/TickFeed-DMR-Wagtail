import asyncio
import logging
import random
import ssl
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import quote

import httpx

from tickfeeddmr.market_data.providers.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
)
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
    from collections.abc import Callable, Iterator, Mapping, Sequence
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
# Таймауты httpx — поштучные на операцию (коннект, каждое чтение сокета),
# а не на запрос целиком: ответ, приходящий "струйкой", может идти сколь
# угодно долго, не нарушая `REQUEST_TIMEOUT_SECONDS` (вживую наблюдался
# `ReadTimeout` через 19–29 с при `timeout=10`). Потолок на всю попытку
# целиком держит `ATTEMPT_DEADLINE_SECONDS` через `asyncio.timeout`. Он
# чуть больше read-таймаута: при нормальном коннекте (~0.1 с) на
# "молчащем" сервере первым срабатывает именованный `httpx.ReadTimeout`
# (~10 с). Но коннект + чтение могут вместе занять до 5 + 10 = 15 с, так
# что при медленном коннекте (SYN-перепосылки, 1–5 с) дедлайн 12 с может
# сработать раньше read-таймаута — тогда причина в логе "TimeoutError
# (attempt deadline 12s exceeded)", а не `ReadTimeout`. Нормальные ответы
# ISS — ~0.4–1.5 с (борд), ~1 с (страница сделок), самый медленный
# успешный в фазе восстановления после сбоя — ~8.7 с.
CONNECT_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0
ATTEMPT_DEADLINE_SECONDS = 12.0

# Повторы одного GET при сетевых сбоях ISS. Периметр MOEX периодически
# недоступен окнами ~60–80 с; большинство отказов в таком окне — быстрые
# `ConnectError`, поэтому именно число попыток × backoff задаёт, какой
# отрезок времени повторы покрывают: 1+2+4+8+8+8 ≈ 31 с (±jitter) — окно,
# кончившееся в пределах этого отрезка, "перепрыгивается" в том же тике.
# Худший случай (каждая попытка упирается в дедлайн) обрезает бюджет
# прогона вызывающего кода (`MOEX_*_POLL_BUDGET_SECONDS`), не клиент.
MAX_ATTEMPTS = 7
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0
BACKOFF_MULTIPLIER = 2
# Мультипликативный jitter ±20%: разводит повторы задач борда и сделок,
# которые стартуют по расписанию с разницей в десятки миллисекунд, почти
# не сокращая покрываемый повторами отрезок (full jitter сократил бы вдвое).
BACKOFF_JITTER = 0.2

# 500–504 — "временные проблемы" по руководству ISS v1.4 (повторить тот же
# адрес через небольшой промежуток); 429 — на случай лимитов, которых в
# документации нет. 501/505 и прочие 5xx — постоянные, повтор бесполезен.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Транспортные ошибки, которые означают ошибку конфигурации, кода или
# доверия, а не сетевой сбой: их не повторяем и пробрасываем как есть,
# чтобы задача падала обычным FAILURE с трейсом, а не превращала проблему
# в вечное "MOEX ISS недоступен" ("raised expected" без трейса).
# - подклассы `httpx.TransportError` — неверная схема в
#   `MOEX_ISS_BASE_URL`, баг в формировании запроса, ошибка прокси
#   (`httpx.ProxyError`: например, 407 — это конфигурация, а не сбой ISS;
#   прокси в проекте не используется, так что его появление — само по
#   себе повод для трейса). Заодно текст `ProxyError`, который может
#   содержать URL прокси с учётными данными, не попадает в наше
#   сообщение `ProviderConnectionError`;
# - причины где-то в цепочке `__cause__`/`__context__` — провал проверки
#   TLS-сертификата httpx отдаёт как обычный `httpx.ConnectError`
#   (`httpx.ConnectError` ← `httpcore.ConnectError` ←
#   `ssl.SSLCertVerificationError`), отличить его можно только по цепочке.
#   Прочие `ssl.SSLError` (обрыв посреди хендшейка и т.п.) и DNS
#   (`socket.gaierror`) остаются повторяемыми — они бывают транзиентными.
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
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(
                REQUEST_TIMEOUT_SECONDS,
                connect=CONNECT_TIMEOUT_SECONDS,
            ),
        )
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
        """GET с повторами; возвращает только успешный (не-ошибочный) ответ.

        Повторяет на `httpx.TransportError` (кроме
        `_NON_RETRYABLE_TRANSPORT_ERRORS` и ошибок с
        `_NON_RETRYABLE_CAUSES` в цепочке причин — те пробрасываются как
        есть), на срабатывании дедлайна попытки и на статусах
        `RETRYABLE_STATUS_CODES`. Прочие ошибочные статусы (4xx, 501, …) —
        сразу `ProviderResponseError` через `_raise_for_status`, без
        повторов. После `MAX_ATTEMPTS` неудач — `ProviderConnectionError`
        с цепочкой от последней ошибки; её короткое описание (тип и
        усечённый текст ошибки, `HTTP <код>` для статуса или дедлайн
        попытки) — в сообщении, в `reason` и в `last_failure_reason`.
        Успех после неудачных попыток — одна строка INFO с итогом
        восстановления (нештатный исход, см. конвенцию логирования в
        `CLAUDE.md`), без записи на каждую попытку.

        `CancelledError` сознательно не перехватывается (он
        `BaseException`, а не `Exception`): если бюджет прогона вызывающего
        кода истёк посреди попытки или паузы между попытками, отмена должна
        прервать цикл повторов, а не превратиться в ещё одну попытку.
        Внутренний `asyncio.timeout` попытки превращает в `TimeoutError`
        только собственное истечение, чужую отмену он пропускает дальше.
        Сырой `TimeoutError` отсюда наружу не выходит никогда — у
        вызывающего кода он однозначно означает его собственный бюджет.
        """
        started = time.monotonic()
        self._last_failure_reason = None
        last_error: Exception | None = None
        reason = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with asyncio.timeout(ATTEMPT_DEADLINE_SECONDS):
                    response = await self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if _is_non_retryable(exc):
                    raise
                last_error, reason = exc, _describe_error(exc)
            except TimeoutError as exc:
                # Только собственный дедлайн попытки: чужая отмена приходит
                # как `CancelledError` и сюда не попадает.
                last_error = exc
                reason = f"attempt deadline {ATTEMPT_DEADLINE_SECONDS:g}s exceeded"
            else:
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    self._raise_for_status(response)
                    if attempt > 1:
                        logger.info(
                            f"MOEX ISS {path}: ответ получен с {attempt}-й попытки "
                            f"за {time.monotonic() - started:.1f} с "
                            f"(последняя ошибка: {reason})",
                        )
                    return response
                # Тело ответа 5xx/429 не логируем на каждой попытке —
                # только код статуса попадёт в итоговую ошибку.
                last_error = ProviderResponseError(
                    f"MOEX ISS request failed with status {response.status_code}",
                )
                reason = f"HTTP {response.status_code}"
            self._last_failure_reason = reason

            if attempt < MAX_ATTEMPTS:
                delay = _backoff_delay(attempt)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"MOEX ISS {path}: попытка {attempt}/{MAX_ATTEMPTS} "
                        f"не удалась ({reason}), повтор через {delay:.1f} с",
                    )
                await asyncio.sleep(delay)

        elapsed = time.monotonic() - started
        msg = (
            f"MOEX ISS unreachable: {reason} "
            f"after {MAX_ATTEMPTS} attempts in {elapsed:.1f}s (GET {path})"
        )
        raise ProviderConnectionError(
            msg,
            reason=reason,
            attempts=MAX_ATTEMPTS,
            elapsed_seconds=elapsed,
        ) from last_error

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

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_error:
            logger.error(
                f"Ошибка MOEX ISS {response.status_code}: {response.text[:500]}",
            )
            msg = f"MOEX ISS request failed with status {response.status_code}"
            raise ProviderResponseError(msg)


def _iter_error_chain(exc: BaseException) -> Iterator[BaseException]:
    """`exc` и его причины по `__cause__`/`__context__`, с защитой от циклов."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_non_retryable(exc: httpx.TransportError) -> bool:
    if isinstance(exc, _NON_RETRYABLE_TRANSPORT_ERRORS):
        return True
    return any(
        isinstance(link, _NON_RETRYABLE_CAUSES) for link in _iter_error_chain(exc)
    )


def _describe_error(exc: httpx.TransportError) -> str:
    """`ConnectError ([Errno 111] Connection refused)` — тип и усечённый текст.

    Текст приводится к одной строке (все пробельные символы, включая
    CR/LF, схлопываются в пробел) и режется до `ERROR_REASON_MAX_CHARS` —
    он попадает в строки лога, и перевод строки внутри позволил бы
    подделать соседнюю запись. Вызывается только для повторяемых ошибок:
    `httpx.ProxyError`, чей текст может содержать URL прокси с учётными
    данными, неповторяемый и сюда не доходит.
    """
    name = type(exc).__name__
    text = " ".join(str(exc).split())[:ERROR_REASON_MAX_CHARS]
    return f"{name} ({text})" if text else name


def _backoff_delay(attempt: int) -> float:
    """Пауза после неудачной попытки `attempt` (с 1): 1, 2, 4, 8, 8, … с ±jitter."""
    base = min(
        MAX_BACKOFF_SECONDS,
        INITIAL_BACKOFF_SECONDS * BACKOFF_MULTIPLIER ** (attempt - 1),
    )
    # Jitter для рассинхронизации повторов, не криптография.
    return base * random.uniform(1 - BACKOFF_JITTER, 1 + BACKOFF_JITTER)  # noqa: S311


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
