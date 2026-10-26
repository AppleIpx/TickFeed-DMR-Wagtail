from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AiConfig(AppConfig):
    name = "tickfeeddmr.ai"
    verbose_name = _("ИИ-аналитик")

    def ready(self) -> None:
        from tickfeeddmr.ai.services.settings import (  # noqa: PLC0415
            validate_ai_settings,
        )

        validate_ai_settings()
