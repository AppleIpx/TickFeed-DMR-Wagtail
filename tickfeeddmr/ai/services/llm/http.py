import functools
import ssl

import certifi
import httpx
from django.conf import settings

_CONNECT_TIMEOUT_SECONDS = 10.0
_WRITE_TIMEOUT_SECONDS = 10.0
_POOL_TIMEOUT_SECONDS = 5.0


def resolve_proxy(prefix: str) -> str | None:
    """Прокси для провайдера: `AI_PROXY_URL`, только если он в белом списке."""
    if prefix in settings.AI_PROXY_PROVIDERS:
        return settings.AI_PROXY_URL or None
    return None


@functools.cache
def gigachat_ssl_context() -> ssl.SSLContext:
    """TLS-контекст GigaChat: certifi плюс корневой сертификат НУЦ Минцифры."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(cafile=settings.GIGACHAT_CA_BUNDLE)
    return ctx


def build_http_client(
    prefix: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Единственная фабрика HTTP-клиента ИИ."""
    return httpx.AsyncClient(
        trust_env=False,
        proxy=resolve_proxy(prefix),
        verify=gigachat_ssl_context() if prefix == "gigachat" else True,
        timeout=httpx.Timeout(
            connect=_CONNECT_TIMEOUT_SECONDS,
            read=settings.AI_READ_TIMEOUT_SECONDS,
            write=_WRITE_TIMEOUT_SECONDS,
            pool=_POOL_TIMEOUT_SECONDS,
        ),
        transport=transport,
    )
