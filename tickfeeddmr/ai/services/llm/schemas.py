from typing import Any, Literal

import msgspec

ProviderKind = Literal["openai_compat", "gigachat"]
Role = Literal["system", "user", "assistant", "tool"]
ToolChoice = Literal["auto", "none"]


class ProviderSpec(msgspec.Struct, frozen=True):
    """Описание провайдера: тип адаптера, адрес и имя настройки с ключом."""

    prefix: str
    kind: ProviderKind
    base_url: str | None
    base_url_setting: str | None
    api_key_setting: str | None
    api_key_required: bool


class ModelRef(msgspec.Struct, frozen=True):
    """Разобранная строка `AI_MODEL`: провайдер + идентификатор модели."""

    provider: str
    model_id: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model_id}"


class ToolCallRequest(msgspec.Struct, frozen=True):
    """Запрос модели на вызов инструмента, уже собранный адаптером целиком."""

    id: str
    name: str
    arguments_json: str


class ChatMessage(msgspec.Struct, frozen=True):
    """Сообщение диалога в нейтральном для провайдеров виде."""

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCallRequest, ...] = ()
    tool_call_id: str | None = None
    # Имя инструмента у `role="tool"`: GigaChat ждёт его в сообщении `function`.
    name: str | None = None


class ToolSpec(msgspec.Struct, frozen=True):
    """Описание инструмента для модели; `parameters` — сырой JSON Schema."""

    name: str
    description: str
    parameters: dict[str, Any]


class TextDelta(msgspec.Struct, frozen=True):
    """Очередной фрагмент текста ответа модели."""

    text: str


class UsageReport(msgspec.Struct, frozen=True):
    """Расход токенов за одно обращение к модели, как его сообщил провайдер."""

    prompt_tokens: int
    completion_tokens: int


ProviderChunk = TextDelta | ToolCallRequest | UsageReport
