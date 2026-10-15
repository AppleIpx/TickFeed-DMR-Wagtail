from django.conf import settings

from tickfeeddmr.ai.services.llm.exceptions import InvalidModelRefError
from tickfeeddmr.ai.services.llm.schemas import ModelRef, ProviderSpec


def parse_model_ref(raw: str) -> ModelRef:
    """Разобрать `provider:model_id` по первому двоеточию."""
    provider, sep, model_id = raw.strip().partition(":")
    if not sep or not provider or not model_id:
        msg = f"expected '<provider>:<model_id>', got {raw!r}"
        raise InvalidModelRefError(msg)
    return ModelRef(provider=provider, model_id=model_id)


def provider_base_url(spec: ProviderSpec) -> str:
    """Базовый URL провайдера без завершающего `/`."""
    url = spec.base_url
    if url is None:
        # base_url_setting обязателен, когда base_url не задан
        url = getattr(settings, spec.base_url_setting or "", "")
    return url.rstrip("/")
