from typing import Literal

import msgspec

ProviderKind = Literal["openai_compat", "gigachat"]


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
