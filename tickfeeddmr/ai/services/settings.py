from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from tickfeeddmr.ai.services.llm.exceptions import InvalidModelRefError
from tickfeeddmr.ai.services.llm.registry import PROVIDERS
from tickfeeddmr.ai.services.llm.resolve import parse_model_ref
from tickfeeddmr.market_data.services.stream_settings import validate_positive

if TYPE_CHECKING:
    from tickfeeddmr.ai.services.llm.schemas import ModelRef

_MIN_TOOL_ITERATIONS = 2
_MAX_TEMPERATURE = 2
_PROXY_SCHEMES = ("http", "https")


def validate_model_ref(raw: str) -> ModelRef:
    """Проверить одну модель: формат, префикс, ключ, CA-файл, адрес."""
    try:
        ref = parse_model_ref(raw)
    except InvalidModelRefError as exc:
        msg = f"AI_MODEL должна иметь вид '<провайдер>:<model_id>', получено {raw!r}"
        raise ImproperlyConfigured(msg) from exc

    spec = PROVIDERS.get(ref.provider)
    if spec is None:
        known = ", ".join(sorted(PROVIDERS))
        msg = f"Провайдер {ref.provider!r} из AI_MODEL неизвестен; допустимые: {known}"
        raise ImproperlyConfigured(msg)

    if (
        spec.api_key_required
        and spec.api_key_setting
        and not getattr(settings, spec.api_key_setting, "")
    ):
        msg = f"Для модели {ref.label!r} нужно задать {spec.api_key_setting}"
        raise ImproperlyConfigured(msg)

    if spec.kind == "gigachat" and not Path(settings.GIGACHAT_CA_BUNDLE).is_file():
        msg = (
            f"GIGACHAT_CA_BUNDLE должна указывать на существующий файл, "
            f"получено {settings.GIGACHAT_CA_BUNDLE!r}"
        )
        raise ImproperlyConfigured(msg)

    if spec.base_url_setting and not getattr(settings, spec.base_url_setting, ""):
        msg = f"Для модели {ref.label!r} нужно задать {spec.base_url_setting}"
        raise ImproperlyConfigured(msg)

    return ref


def validate_ai_settings() -> None:
    """Проверить конфигурацию ИИ при старте процесса."""
    for name in (
        "AI_DAILY_REQUEST_LIMIT",
        "AI_DAILY_TOKEN_LIMIT",
        "AI_MAX_TOOL_CALLS_PER_STEP",
        "AI_MAX_HISTORY_MESSAGES",
        "AI_MAX_MESSAGE_CHARS",
        "AI_MAX_HISTORY_CHARS",
        "AI_STEP_COMPLETION_RESERVE_TOKENS",
        "AI_TOOL_MAX_ROWS",
        "AI_READ_TIMEOUT_SECONDS",
        "AI_CHAT_DEADLINE_SECONDS",
    ):
        validate_positive(name, getattr(settings, name))

    if settings.AI_MAX_HISTORY_CHARS < settings.AI_MAX_MESSAGE_CHARS:
        msg = (
            f"AI_MAX_HISTORY_CHARS ({settings.AI_MAX_HISTORY_CHARS}) не может быть "
            f"меньше AI_MAX_MESSAGE_CHARS ({settings.AI_MAX_MESSAGE_CHARS})"
        )
        raise ImproperlyConfigured(msg)

    if settings.AI_STEP_COMPLETION_RESERVE_TOKENS >= settings.AI_DAILY_TOKEN_LIMIT:
        msg = (
            f"AI_STEP_COMPLETION_RESERVE_TOKENS "
            f"({settings.AI_STEP_COMPLETION_RESERVE_TOKENS}) должна быть меньше "
            f"AI_DAILY_TOKEN_LIMIT ({settings.AI_DAILY_TOKEN_LIMIT})"
        )
        raise ImproperlyConfigured(msg)

    if settings.AI_MAX_TOOL_ITERATIONS < _MIN_TOOL_ITERATIONS:
        msg = (
            f"AI_MAX_TOOL_ITERATIONS должна быть не меньше {_MIN_TOOL_ITERATIONS} "
            f"(один шаг с инструментами плюс финальный ответ), "
            f"получено {settings.AI_MAX_TOOL_ITERATIONS}"
        )
        raise ImproperlyConfigured(msg)

    if not 0 <= settings.AI_TEMPERATURE <= _MAX_TEMPERATURE:
        msg = (
            f"AI_TEMPERATURE должна быть в диапазоне [0, 2], "
            f"получено {settings.AI_TEMPERATURE}"
        )
        raise ImproperlyConfigured(msg)

    unknown = [p for p in settings.AI_PROXY_PROVIDERS if p not in PROVIDERS]
    if unknown:
        msg = (
            f"AI_PROXY_PROVIDERS содержит неизвестных провайдеров: "
            f"{', '.join(unknown)}; "
            f"допустимые: {', '.join(sorted(PROVIDERS))}"
        )
        raise ImproperlyConfigured(msg)

    sdk_managed = [
        p for p in settings.AI_PROXY_PROVIDERS if PROVIDERS[p].kind == "gigachat"
    ]
    if sdk_managed:
        msg = (
            f"AI_PROXY_PROVIDERS не может содержать {', '.join(sdk_managed)}: "
            f"клиент SDK GigaChat не использует AI_PROXY_URL"
        )
        raise ImproperlyConfigured(msg)

    proxy_url = settings.AI_PROXY_URL
    if proxy_url and urlsplit(proxy_url).scheme not in _PROXY_SCHEMES:
        msg = (
            "AI_PROXY_URL должен начинаться с http:// или https:// "
            "(для socks-прокси нужен пакет 'socksio', он не установлен)"
        )
        raise ImproperlyConfigured(msg)

    if settings.AI_ENABLED:
        validate_model_ref(settings.AI_MODEL)
