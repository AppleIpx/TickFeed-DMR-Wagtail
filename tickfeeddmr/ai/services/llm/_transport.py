import asyncio
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx
import msgspec

from tickfeeddmr.ai.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_ATTEMPTS = 2
_RETRY_STATUSES = frozenset({429, 502, 503, 504})
_DEFAULT_RETRY_DELAY_SECONDS = 1.5
_MAX_RETRY_DELAY_SECONDS = 5.0
_ERROR_BODY_CHARS = 300


def one_line(text: str, limit: int = _ERROR_BODY_CHARS) -> str:
    """Свести текст в одну строку и обрезать для лога."""
    return " ".join(text.split())[:limit]


def retry_delay(response: httpx.Response) -> float:
    """Пауза перед повтором: `Retry-After` в секундах, не больше 5 с."""
    try:
        delay = float(response.headers.get("retry-after", ""))
    except ValueError:
        return _DEFAULT_RETRY_DELAY_SECONDS
    return min(max(delay, 0.0), _MAX_RETRY_DELAY_SECONDS)


def map_status(response: httpx.Response) -> LLMError:
    """Ошибка слоя по HTTP-статусу ответа (тело уже прочитано)."""
    code = response.status_code
    if code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
        return LLMAuthError(f"ИИ-провайдер отклонил ключ доступа: HTTP {code}")
    if code == HTTPStatus.TOO_MANY_REQUESTS or code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return LLMConnectionError(f"ИИ-провайдер недоступен: HTTP {code}")
    msg = f"ИИ-провайдер вернул HTTP {code}: {one_line(response.text)}"
    return LLMResponseError(msg)


@asynccontextmanager
async def open_stream(
    client: httpx.AsyncClient,
    url: str,
    *,
    body: dict[str, Any],
    headers: dict[str, str],
) -> AsyncIterator[httpx.Response]:
    """Открыть потоковый POST с одним повтором — только до первого байта ответа."""
    content = msgspec.json.encode(body)
    headers = {**headers, "Content-Type": "application/json"}
    yielded = False
    for attempt in range(1, _ATTEMPTS + 1):
        last = attempt == _ATTEMPTS
        try:
            request = client.stream("POST", url, content=content, headers=headers)
            async with request as resp:
                if resp.status_code in _RETRY_STATUSES and not last:
                    delay = retry_delay(resp)
                else:
                    if resp.status_code >= HTTPStatus.BAD_REQUEST:
                        await resp.aread()
                        raise map_status(resp)
                    yielded = True
                    yield resp
                    return
        except httpx.TransportError as exc:
            if yielded or last:
                msg = f"Не удалось связаться с ИИ-провайдером: {type(exc).__name__}"
                raise LLMConnectionError(msg) from exc
            delay = _DEFAULT_RETRY_DELAY_SECONDS
        await asyncio.sleep(delay)
