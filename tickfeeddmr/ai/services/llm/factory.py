from typing import TYPE_CHECKING

from django.conf import settings

from tickfeeddmr.ai.services.llm.gigachat import GigaChatProvider
from tickfeeddmr.ai.services.llm.http import build_http_client
from tickfeeddmr.ai.services.llm.openai_compat import OpenAICompatProvider
from tickfeeddmr.ai.services.llm.registry import PROVIDERS
from tickfeeddmr.ai.services.llm.resolve import parse_model_ref

if TYPE_CHECKING:
    import httpx2

    from tickfeeddmr.ai.services.llm.base import LLMProvider
    from tickfeeddmr.ai.services.llm.schemas import ModelRef


def build_provider(
    model_ref: str | ModelRef,
    *,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> LLMProvider:
    """Единственное место, где по `AI_MODEL` выбирается класс адаптера.

    `transport` относится только к провайдерам на `openai`: клиент SDK GigaChat
    создаёт сам, в тестах подменяется его метод.
    """
    ref = parse_model_ref(model_ref) if isinstance(model_ref, str) else model_ref
    spec = PROVIDERS[ref.provider]
    api_key = getattr(settings, spec.api_key_setting) if spec.api_key_setting else None
    if spec.kind == "gigachat":
        return GigaChatProvider(
            spec=spec,
            model_id=ref.model_id,
            credentials=api_key or "",
        )
    return OpenAICompatProvider(
        spec=spec,
        model_id=ref.model_id,
        api_key=api_key,
        client=build_http_client(ref.provider, transport=transport),
    )
