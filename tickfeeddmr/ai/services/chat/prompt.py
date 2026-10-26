from typing import TYPE_CHECKING

from tickfeeddmr.ai.services.chat.prompt_text import (
    ANALYST_SYSTEM_PROMPT,
    TODAY_PLACEHOLDER,
)

if TYPE_CHECKING:
    from datetime import date


def build_system_prompt(today: date) -> str:
    """Системный промпт с подставленной датой."""
    return ANALYST_SYSTEM_PROMPT.replace(TODAY_PLACEHOLDER, today.isoformat())
