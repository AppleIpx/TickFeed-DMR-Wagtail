import math

CHARS_PER_TOKEN = 3


def estimate_tokens(chars: int) -> int:
    """Грубая оценка токенов по числу символов, если провайдер не прислал usage."""
    return math.ceil(chars / CHARS_PER_TOKEN)
