from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.llm.schemas import ProviderSpec

if TYPE_CHECKING:
    from collections.abc import Mapping

GIGACHAT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

PROVIDERS: Mapping[str, ProviderSpec] = {
    spec.prefix: spec
    for spec in (
        # У GigaChat свой OAuth, свой CA и формат `functions` — отдельный адаптер
        # и отдельные настройки `GIGACHAT_*`.
        ProviderSpec(
            prefix="gigachat",
            kind="gigachat",
            base_url="https://gigachat.devices.sberbank.ru/api/v1",
            base_url_setting=None,
            api_key_setting="GIGACHAT_CREDENTIALS",
            api_key_required=True,
        ),
        # Любой OpenAI-совместимый сервис (OpenRouter, Groq, Gemini, DeepSeek,
        # Ollama, vLLM, ...): адрес и ключ — `AI_BASE_URL` / `AI_API_KEY`.
        ProviderSpec(
            prefix="custom",
            kind="openai_compat",
            base_url=None,
            base_url_setting="AI_BASE_URL",
            api_key_setting="AI_API_KEY",
            api_key_required=False,
        ),
    )
}
