import functools

from django.conf import settings
from gigachat import GigaChatAsyncClient

from tickfeeddmr.ai.services.llm.http import gigachat_ssl_context
from tickfeeddmr.ai.services.llm.registry import GIGACHAT_OAUTH_URL


@functools.cache
def get_sdk_client(
    base_url: str,
    credentials: str,
    scope: str,
) -> GigaChatAsyncClient:
    """Клиент SDK на процесс: токен хранится в нём и переиспользуется."""
    return GigaChatAsyncClient(
        base_url=base_url,
        auth_url=GIGACHAT_OAUTH_URL,
        credentials=credentials,
        scope=scope,
        ssl_context=gigachat_ssl_context(),
        timeout=settings.AI_READ_TIMEOUT_SECONDS,
        max_retries=1,
    )
